"""Three independent seed shards, merged only after all paired cells complete."""
import argparse,concurrent.futures,csv,itertools,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--training',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    protocol=json.loads((HERE/'protocol.json').read_text());a.output.mkdir(parents=True,exist_ok=False)
    def job(seed):
        env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
        out=a.output/f'seed-{seed}'
        with (a.output/f'seed-{seed}.log').open('w') as f:
            subprocess.run([sys.executable,str(HERE/'evaluate.py'),'--training',str(a.training),'--output',str(out),'--seed',str(seed)],
                stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
        assert json.loads((out/'complete.json').read_text())['episodes']==216
        print('evaluation seed',seed,'216 episodes completed',flush=True)
        with (out/'episodes.csv').open() as f:return list(csv.DictReader(f))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows=[r for shard in pool.map(job,protocol['seeds']) for r in shard]
    keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']) for r in rows]
    expected=set(itertools.product(protocol['seeds'],protocol['speeds'],protocol['paths'],protocol['scenarios'],protocol['methods']))
    assert len(keys)==len(set(keys))==len(expected)==648 and set(keys)==expected
    with (a.output/'episodes.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
    (a.output/'complete.json').write_text(json.dumps(dict(episodes=len(rows),protocol=protocol,final_reserved=False,native=False),indent=2)+'\n')


if __name__=='__main__':main()
