"""Regenerate cooperative sensor inputs independently of the following controller."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import zlib
import numpy as np
from .scenarios import Scene,radar_scan
from .perception import encode_peer_scan,decode_peer_scan


def check(path):
    path=Path(path);spec=json.loads((path/'case.json').read_text());scene=Scene(spec['case'],spec['speed'],spec['seed'])
    data=[json.loads(s) for s in (path/'ticks.jsonl').read_text().splitlines()]
    rngs={name:np.random.default_rng(np.random.SeedSequence([spec['seed'],41,zlib.crc32(name.encode())])) for name in scene.connected}
    expected={};count=0
    for row in data:
        now=row['time_s'];tick=row['tick'];ego=np.array(row['before']);traffic=scene.states(now)
        if tick%2==0 and not(scene.profile.radio_blackout and 11.<=now<12.5):
            for name in scene.connected:
                if np.linalg.norm(traffic[name][:2]-ego[:2])>150.:continue
                others={**traffic,'follower':ego};others.pop(name)
                scan=radar_scan(tick//2,now,traffic[name],others,scene.profile,rngs[name])
                expected[name,scan.sequence]=encode_peer_scan(name,scan)
        for event in row['peer_scans']:
            raw=event['message'].encode();name,scan=decode_peer_scan(raw)
            assert raw==expected.pop((name,scan.sequence)),'Cooperative sensor bytes differ from observed fixture'
            assert abs(now-scan.observed_s-.05)<1e-8
            count+=1
    assert not expected,'Missing cooperative inputs'
    return count


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('study');p.add_argument('--stage',choices=('development','validation'),required=True);a=p.parse_args()
    root=Path(a.study)/a.stage;summary=json.loads((root/'summary.json').read_text())
    paths=[str(root/f"{r['case']}-{r['speed']:g}-{r['seed']}") for r in summary['results']]
    with ProcessPoolExecutor(max_workers=3) as pool:counts=list(pool.map(check,paths))
    print(json.dumps(dict(passed=True,episodes=len(paths),regenerated_cooperative_datagrams=sum(counts))))


if __name__=='__main__':main()
