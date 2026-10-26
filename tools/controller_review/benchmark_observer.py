"""Paired implementation microbenchmark, not a real-time deadline test."""
import argparse,csv,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from realtime_kernels import measure_fast,np
from kernels import measure,path_values
from data import G


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
    path=tuple(float(v) for v in G['paths']['dlc220']);y,h,_=path_values(80.,path)
    state=np.array([80.,y+.1,h+.01,.01,.02,.03]);est=np.zeros(4);cov=np.eye(4)*.01;prev=np.zeros(4);noise=np.array([.01,.001,.001,.05])
    args=(state,20.,path,noise,0,est,cov,prev,False,1.)
    for _ in range(100):measure(*args);measure_fast(*args)
    rows=[];rng=np.random.default_rng(985)
    for pair in range(2000):
        methods=[('original',measure),('small_algebra',measure_fast)]
        if rng.integers(2):methods.reverse()
        outputs=[]
        for name,fn in methods:
            cpu=time.thread_time_ns();start=time.perf_counter_ns();output=fn(*args);end=time.perf_counter_ns();cpu_end=time.thread_time_ns()
            rows.append(dict(pair=pair,method=name,wall_ns=end-start,cpu_ns=cpu_end-cpu));outputs.append(output)
        if pair%100==0:
            for before,after in zip(*outputs):np.testing.assert_allclose(before,after,atol=1e-11,rtol=1e-10)
    with (a.output/'samples.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    result=dict(scope='2000 randomized-order warm pairs on one fixed input; not native or deadline evidence',methods={})
    for name in ('original','small_algebra'):
        subset=[r for r in rows if r['method']==name];result['methods'][name]={}
        for clock in ('wall_ns','cpu_ns'):
            values=np.array([r[clock] for r in subset])/1e6
            result['methods'][name][clock]=dict(median_ms=float(np.median(values)),p99_ms=float(np.quantile(values,.99)),max_ms=float(values.max()))
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
