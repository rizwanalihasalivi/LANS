"""Fixed training-only alignment/feedback calibration; no PPO training."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import json,hashlib,shutil,multiprocessing as mp
import numpy as np
from integrations.unified_lans.run import clean
from tools.unified_control_v4.calibrate import cases
from tools.unified_control_v9.learning import run_episode
from .longitudinal import Synchronous
from .fast_cost import Controller as Prior
from .aligned import Controller

ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/v8-four-gates/aligned-calibration-v2'
ARMS={'lqr':{},'prior':{},**{f'aligned-w{w:g}-cap{cap:g}':dict(feedback_weight=w,secondary_factor=cap) for w in (0.,.5,1.) for cap in (1.,1.075)}}
def write(p,v):p.write_text(json.dumps(clean(v),indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(job):
    c,arm=job;d=OUT/f'{arm}-{c["id"]:02d}';d.mkdir();kw=dict(barrier_frequency=3.,quality_factor=1.1,secondary_factor=1.075,early_id=True,tracking_only=False,adaptive=arm!='lqr',mpc=arm!='lqr');kw.update(ARMS[arm])
    cls=Synchronous if arm=='lqr' else Prior if arm=='prior' else Controller
    r,rows=run_episode(c,'lqr' if arm=='lqr' else 'deterministic',grid=arm!='lqr',controller_factory=cls,controller_kwargs=kw)
    raw=d/'ticks.jsonl';raw.write_text(''.join(json.dumps(clean(x),allow_nan=False)+'\n' for x in rows));r.update(arm=arm,raw_sha256=sha(raw));write(d/'summary.json',r);return r


def main():
    OUT.mkdir(parents=True,exist_ok=False);cc=cases();files=[*Path(__file__).parent.glob('*.py'),*Path(__file__).parent.glob('*.md'),*Path(ROOT/'integrations/unified_lans').glob('*.py')]
    for v in range(4,10):files.extend(Path(ROOT/f'tools/unified_control_v{v}').glob('*.py'))
    files.extend(Path(ROOT/'tools/v8_reliability').glob('*.py'));hashes={str(p.relative_to(ROOT)):sha(p) for p in files}
    write(OUT/'plan.json',dict(cases=cc,arms=ARMS,sources=hashes,expected_records=512,scope='exposed training calibration, no PPO models or final outcomes',selector='zero failures, every-case progress>=99%, both mean quality metrics no higher than matched LQR, then smallest RMSE;5%gain reported separately'))
    for p in files:d=OUT/'source'/p.relative_to(ROOT);d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
    jobs=[(c,a) for c in cc for a in ARMS];results=[]
    with ProcessPoolExecutor(max_workers=4,mp_context=mp.get_context('spawn')) as pool:
        for i,f in enumerate(as_completed([pool.submit(run,j) for j in jobs]),1):
            results.append(f.result())
            if i%32==0:print('ALIGNED CALIBRATION',i,'/512',flush=True)
    write(OUT/'summary.json',results);base={r['case']['id']:r for r in results if r['arm']=='lqr'};scores=[]
    for arm in ARMS:
        sub=[r for r in results if r['arm']==arm];ratios={f:float(np.mean([r[f] for r in sub])/np.mean([r[f] for r in base.values()])) for f in ('rmse_m','heading_rms','rate_rms')}
        progress=min(r['progress_m']/base[r['case']['id']]['progress_m'] for r in sub);failures=sum(r['failed'] for r in sub);eligible=failures==0 and progress>=.99 and ratios['heading_rms']<=1 and ratios['rate_rms']<=1
        scores.append(dict(arm=arm,ratios=ratios,failures=failures,minimum_progress_ratio=progress,eligible=bool(eligible),tracking_pass=ratios['rmse_m']<=.95))
    write(OUT/'selection.json',dict(scores=scores));print(json.dumps(scores),flush=True)
    for n,h in hashes.items():assert sha(ROOT/n)==h


if __name__=='__main__':main()
