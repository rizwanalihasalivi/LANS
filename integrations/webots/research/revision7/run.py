"""Execute the frozen headroom grid in three noise-seed shards; no learning."""
import argparse,concurrent.futures,csv,gzip,itertools,json,math,os,subprocess,sys,time
from pathlib import Path
import numpy as np
from bootstrap import HERE,RESEARCH
from comparison import configure_lqr
from core import GAINS
from kernels import simulate
P=json.loads((HERE/'protocol.json').read_text())
GRID=json.loads((RESEARCH/'revision6/protocol.json').read_text())
HEADERS=['tick','state_time_s','x','y','heading','reference','error','command','actuator','baseline','weight',
    'reason_code','proposal','selected_index','cost_m008','cost_m004','cost_zero','cost_p004','cost_p008',
    'packet_sequence','observed_time','pending_sequence','gate_good']


def shard(seed,out):
    configure_lqr();gains=np.array([GAINS[v] for v in (15,20,25)])
    candidates=np.array(P['residual_candidates_rad']);out.mkdir(parents=True,exist_ok=False);(out/'traces').mkdir()
    rows=[]
    with (out/'episodes.csv').open('w',newline='') as f:
        writer=None
        for speed,path_name,region in itertools.product(GRID['speeds'],GRID['paths'],GRID['scenarios']):
            case=GRID['scenarios'][region];path=tuple(float(v) for v in GRID['paths'][path_name]);scheduled=math.ceil((220/speed+2)/.01)
            noise_seed=GRID['development_noise_base']+GRID['seeds'].index(seed)*10000+speed*100+list(GRID['paths']).index(path_name)*10+list(GRID['scenarios']).index(region)
            scales=np.array([.03,math.radians(.17),.01,.1])*case['noise']
            noises=np.random.default_rng(noise_seed).normal(0,scales,size=(scheduled+P['lookahead_ticks']+1,4))
            for index,method in enumerate(P['methods']):
                start=time.perf_counter()
                trace,failed,calls=simulate(index,float(speed),path,case['mu'],case['stiffness'],float(case['noise']),
                    case['sensor_delay_steps'],case['service_ticks'],noises,gains,candidates,P['lookahead_ticks'],scheduled)
                wall=time.perf_counter()-start;errors=trace[:,6];correction=trace[:,7]-trace[:,9]
                if region=='latency100':assert np.array_equal(trace[:,7],trace[:,9])
                rates=np.abs(np.diff(np.r_[0.,trace[:,8]]))/.01
                assert np.isfinite(errors).all() and max(rates)<=.3500001
                if method.startswith('oracle') or (seed==GRID['seeds'][0] and speed==25 and path_name=='dlc220'):
                    file=out/'traces'/f'{speed}-{path_name}-{region}-{method}.csv.gz'
                    with gzip.open(file,'wt',newline='') as stream:
                        w=csv.writer(stream,lineterminator='\n');w.writerow(HEADERS);w.writerows(trace)
                counts=np.bincount(trace[:,11].astype(np.int64),minlength=11)
                hist=np.bincount(trace[trace[:,13]>=0,13].astype(np.int64),minlength=5)
                row=dict(seed=seed,noise_seed=noise_seed,speed=speed,path=path_name,scenario=region,method=method,
                    survived=not failed,steps=len(errors),scheduled_steps=scheduled,rmse=float(np.sqrt(np.mean(errors**2))),
                    penalized_rmse=float(np.sqrt((sum(errors**2)+(scheduled-len(errors))*6.25)/scheduled)),
                    active_fraction=float(np.mean(trace[:,10]>0)),mean_weight=float(np.mean(trace[:,10])),
                    correction_rms_rad=float(np.sqrt(np.mean(correction**2))),max_rate=float(max(rates)),
                    selector_calls=calls,branch_rollouts=calls*5,branch_control_ticks=calls*5*P['lookahead_ticks'],
                    wall_s=wall,selection_counts=json.dumps(hist.tolist()),reason_counts=json.dumps(counts.tolist()))
                if writer is None:writer=csv.DictWriter(f,fieldnames=row,lineterminator='\n');writer.writeheader()
                writer.writerow(row);f.flush();rows.append(row)
            print(f'seed{seed} v{speed} {path_name} {region}: {len(rows)} episodes',flush=True)
    assert len(rows)==288
    (out/'complete.json').write_text(json.dumps(dict(episodes=len(rows),seed=seed,protocol=P),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--seed',type=int,choices=GRID['seeds']);a=parser.parse_args()
    if a.seed is not None:shard(a.seed,a.output);return
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'protocol.json').write_text((HERE/'protocol.json').read_text())
    (a.output/'grid.json').write_text(json.dumps(GRID,indent=2)+'\n')
    sources=list(HERE.glob('*.py'))+[RESEARCH/'core.py',RESEARCH/'protocol.json',RESEARCH/'comparison.py',RESEARCH/'comparison-protocol.json',
        RESEARCH/'revision2/gating.py',RESEARCH/'revision2/plant.py',RESEARCH/'revision5/execution.py']
    for source in sources:
        target=a.output/'source'/source.relative_to(RESEARCH);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
    def job(seed):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (a.output/f'seed-{seed}.log').open('w') as stream:
            subprocess.run([sys.executable,str(HERE/'run.py'),'--seed',str(seed),'--output',str(a.output/f'seed-{seed}')],
                check=True,env=env,stdout=stream,stderr=subprocess.STDOUT)
        print('seed',seed,'288 episodes complete',flush=True)
        with (a.output/f'seed-{seed}/episodes.csv').open() as stream:return list(csv.DictReader(stream))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows=[r for group in pool.map(job,GRID['seeds']) for r in group]
    assert len(rows)==864
    with (a.output/'episodes.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=P,training=False,reserved=False,native=False),indent=2)+'\n')


if __name__=='__main__':main()
