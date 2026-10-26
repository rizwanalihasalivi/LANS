import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);protocol=json.loads((HERE/'protocol.json').read_text())
    def job(seed):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        with (a.output/f'{seed}.log').open('w') as f:
            subprocess.run([sys.executable,str(HERE/'student.py'),'--data',str(a.data),'--seed',str(seed),'--output',str(a.output/str(seed))],
                env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
        print('student',seed,'complete',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(job,protocol['student']['seeds']))
    (a.output/'complete.json').write_text(json.dumps(dict(students=protocol['student']['seeds'],epochs_each=20,protocol=protocol),indent=2)+'\n')


if __name__=='__main__':main()
