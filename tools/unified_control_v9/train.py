"""Run exactly the three declared continuation endpoints, retaining each one."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,multiprocessing as mp
from .control import Controller
from .learning import train_endpoint,SEEDS
from integrations.unified_lans.inference import sha

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'results/publication-v9'


def selected_kwargs():
    selected=json.loads((DATA/'calibration/selection.json').read_text())['selected']
    assert selected is not None,'No eligible asynchronous controller; do not train a disqualified replacement'
    return dict(quality_factor=selected['quality_factor'],guard_factor=selected['guard_factor'],
        nominal_feedback=selected['nominal_feedback'],early_id=True,tracking_only=False,planner_backend='logical')


def worker(seed):
    folder=DATA/'policies'/f'seed-{seed}'
    if (folder/'manifest.json').exists():
        record=json.loads((folder/'manifest.json').read_text());assert sha(folder/'policy.zip')==record['policy_sha256']
        assert record['new_steps']==16384;return record
    return train_endpoint(seed,folder,Controller,selected_kwargs())


def main():
    selected_kwargs();(DATA/'policies').mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn')) as pool:
        records=[]
        for f in as_completed([pool.submit(worker,seed) for seed in SEEDS]):
            record=f.result();records.append(record);print('FIXED ENDPOINT COMPLETE',record['seed'],record['new_steps'],flush=True)
    records.sort(key=lambda r:r['seed'])
    (DATA/'policies/summary.json').write_text(json.dumps(records,indent=2))
    print('All 49152 additional training steps complete; no seed or checkpoint selection.',flush=True)


if __name__=='__main__':main()
