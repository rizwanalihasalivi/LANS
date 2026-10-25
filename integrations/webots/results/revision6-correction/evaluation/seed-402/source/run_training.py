"""Run only the six predeclared100k jobs, at most two CPU processes."""
import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((HERE/'protocol.json').read_text())
    def job(arm,seed):
        name=f'{arm}-{seed}'
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        with (a.output/(name+'.log')).open('w') as stream:
            subprocess.run([sys.executable,str(HERE/'train.py'),'--arm',arm,'--seed',str(seed),'--output',str(a.output/name)],
                check=True,stdout=stream,stderr=subprocess.STDOUT,env=env)
        result=json.loads((a.output/name/'complete.json').read_text());assert result['steps']==100000
        print(name,'completed',round(result['wall_s'],2),'seconds',flush=True)
        return dict(arm=arm,seed=seed,steps=result['steps'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(job,arm,seed) for seed in protocol['seeds'] for arm in protocol['arms']]
        results=[future.result() for future in concurrent.futures.as_completed(futures)]
    assert len(results)==6 and sum(r['steps'] for r in results)==600000
    (a.output/'complete.json').write_text(json.dumps(dict(jobs=results,total_training_steps=600000),indent=2)+'\n')


if __name__=='__main__':main()
