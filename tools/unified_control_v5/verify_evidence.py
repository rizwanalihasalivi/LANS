"""Check sealed archives; optionally recompute restored campaign results read-only."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).parent / 'evidence'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_archives():
    count = 0
    for line in (EVIDENCE / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        path = EVIDENCE / name
        assert digest(path.read_bytes()) == expected, ('archive hash', name)
        with ZipFile(path) as archive:
            manifest_name = 'EVIDENCE_MANIFEST.json'
            names = archive.namelist()
            assert len(names) == len(set(names)), ('duplicate member', name)
            manifest = json.loads(archive.read(manifest_name))['files']
            assert set(manifest) == set(names) - {manifest_name}
            assert archive.testzip() is None, ('CRC failure', name)
            for member, record in manifest.items():
                parts = Path(member).parts
                assert not Path(member).is_absolute() and '..' not in parts
                data = archive.read(member)
                assert len(data) == record['size'] and digest(data) == record['sha256'], member
                count += 1
        print(name, 'SHA256, CRC and member manifest: PASS')
    print(count, 'archive members verified')


def verify_campaigns():
    # The original evaluator fixes bootstrap seed, cluster definition and gates.
    from tools.unified_campaign.campaign import assess
    from integrations.unified_lans.physics import Command, advance, errors
    from tools.unified_campaign import study
    import numpy as np

    for version in (4, 5):
        root = ROOT / f'results/corridor-v{version}/confirmation-campaign'
        protocol_data = (root / 'protocol.json').read_bytes()
        protocol = json.loads(protocol_data)
        for name, expected in protocol['source_hashes'].items():
            assert digest((root / 'source' / name).read_bytes()) == expected, name
        for actor, expected in protocol['models'].items():
            path = ROOT / f'results/python-campaign-v2/policies/seed-{actor}/policy.zip'
            assert digest(path.read_bytes()) == expected, path
        episodes = 0
        total_ticks = 0
        for stage in ('regression-development', 'regression-stress', 'development', 'stress'):
            results = json.loads((root / f'{stage}_summary.json').read_text())
            expected_episodes = 352 if stage == 'development' else (160 if stage == 'regression-development' else 120)
            assert len(results) == expected_episodes
            seen = set()
            for record in results:
                key = f"{record['case']['id']:03d}-{record['mode']}-{record['actor']}"
                assert key not in seen
                seen.add(key)
                assert record == json.loads((root / stage / (key + '.json')).read_text())
                raw = (root / stage / (key + '.jsonl')).read_bytes()
                assert digest(raw) == record['raw_sha256']
                assert digest(protocol_data) == record['protocol_sha256']
                rows = [json.loads(line) for line in raw.splitlines()]
                assert len(rows) == record['ticks']
                state = np.array(rows[0]['state_before'])
                case = record['case']
                route = study.StudyRoute(study.initial(case['scenario'])[0].kind,
                                         case['mirror'], case['phase'], case['amplitude'])
                previous = Command()
                previous_issued = Command()
                pending = []
                for i, row in enumerate(rows):
                    assert row['tick'] == i and row['time_s'] == i * .05
                    np.testing.assert_allclose(state, row['state_before'], rtol=0, atol=1e-12)
                    issued = Command(row['issued_steering'], row['issued_accel'])
                    assert abs(issued.steering - previous_issued.steering) <= .03 + 1e-10
                    assert abs(issued.steering) <= .5 and -6 <= issued.accel <= 2.5
                    pending.append((row['time_s'] + case['delay'], issued))
                    while pending and pending[0][0] <= row['time_s'] + 1e-9:
                        _, previous = pending.pop(0)
                    actual = Command(row['applied_steering'], row['applied_accel'])
                    assert previous == actual
                    state = advance(state, actual, .05, case['stiffness'])
                    np.testing.assert_allclose(state, row['state_after'], rtol=0, atol=1e-12)
                    err, _ = errors(state, route)
                    assert abs(err[0] - row['error']) < 1e-12
                    if row['source'] == 'ppo':
                        assert row['proposal_age'] < .15 and row['proposal_wall_age'] < .15
                        assert not row['ego_backup']
                    if row['ego_backup']:
                        assert row['source'] in ('backup_lqr', 'hold_brake')
                        assert issued.accel == -6 and row['residual'] == 0
                    previous_issued = issued
                n = record['expected_ticks']
                rmse = math.sqrt((sum(r['error'] ** 2 for r in rows) + (n - len(rows)) * 2.5 ** 2) / n)
                assert abs(rmse - record['rmse_m']) < 1e-12
                failed = len(rows) < n or any(r['collision'] or abs(r['error']) > 1.75 for r in rows)
                assert failed == record['failed']
                assert sum(r['collision'] for r in rows) == record['collisions']
                if record['mode'] == 'hybrid':
                    assert not failed
                total_ticks += len(rows)
            if stage == 'development':
                gate = assess(results)
                assert gate == json.loads((root / 'development_gate.json').read_text())
                assert not gate['passed']  # These archived runs did not pass promotion.
            episodes += len(results)
        assert episodes == 752 and total_ticks == 90240
        status = json.loads((root / 'STATUS.json').read_text())
        assert not status['development_passed']
        assert all(status[name] == 'NOT_RUN' for name in ('reserved', 'wall_worker', 'webots'))
        print(f'v{version}: {episodes} episodes/{total_ticks} ticks verified; safety PASS, promotion FAIL')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaigns', action='store_true')
    args = parser.parse_args()
    verify_archives()
    if args.campaigns:
        verify_campaigns()


if __name__ == '__main__':
    main()
