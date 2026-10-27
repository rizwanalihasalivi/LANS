"""Replay raw/prospective inputs, exact actor outputs, plant and metrics."""
import boot7
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import statistics
from study7 import CompEnv,P
from laptop_full_controller import load_portable,np

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=boot7.Path,required=True);a=p.parse_args();out=a.run
    rows=list(csv.DictReader((out/'episodes.csv').open()));cfg=P['development']
    keys={(int(r['seed']),int(r['mirror']),float(r['service_s']),r['source']) for r in rows}
    assert len(rows)==len(keys)==72 and keys==set(itertools.product(cfg['seeds'],cfg['mirrors'],cfg['services_s'],cfg['sources']))
    actor=load_portable(out/'actor');actor.golden_check();ticks=queries=exact=0;traces={}
    for row in rows:
        with gzip.open(out/'traces'/row['trace'],'rt') as f:rr=list(csv.DictReader(f))
        source=row['source'];seed=int(row['seed']);sign=int(row['mirror']);service=float(row['service_s']);n=len(rr);h=int(row['scheduled'])
        env=CompEnv((20,'dlc220',sign,'nominal',int(row['noise_id'])),source,service);env.reset();model=actor.load(seed)
        for r in rr:
            raw=np.array([float(r[f'obs{i}']) for i in range(20)],np.float32);np.testing.assert_array_equal(raw,env.obs)
            if r['submitted']=='True':
                expected=raw.copy()
                if source=='compensated':
                    expected,meta=env.ctrl.prepare_query(raw,env.estimate,env.state[5],env.measured_speed,env.ctrl.previews,env.gain)
                    assert meta==json.loads(r['query_metadata_json'])
                np.testing.assert_array_equal(expected,np.array(json.loads(r['query_json']),np.float32))
                assert np.all(expected[[15,16,17,19]]==0)
                if source!='lqr':
                    residual=[-.08,-.04,0.,.04,.08][int(actor.logits(model,expected[None,:]).argmax(1)[0])]
                    assert abs(residual-float(r['proposed_residual']))<1e-12;queries+=1
            _,_,_,_,checked=env.step_residual(float(r['proposed_residual']))
            for field in ('command','baseline','filtered_residual','weight','actuator','x','y','heading','reward','lateral_error','heading_error','steering_rate'):
                assert abs(float(r[field])-checked[field])<1e-11,(row['trace'],r['tick'],field)
            assert r['reason']==checked['reason']
            if float(r['weight']):assert 0<=float(r['packet_age_s'])<.05
            ticks+=1
        expected=dict(rmse_m=math.sqrt((sum(float(r['lateral_error'])**2 for r in rr)+(h-n)*6.25)/h),
            heading_rmse_rad=math.sqrt(sum(float(r['heading_error'])**2 for r in rr)/n),rate_rms_rad_s=math.sqrt(sum(float(r['steering_rate'])**2 for r in rr)/n))
        for k,v in expected.items():assert abs(v-float(row[k]))<1e-12
        traces[(seed,sign,service,source)]=rr
    for seed,sign in itertools.product(cfg['seeds'],cfg['mirrors']):
        base=traces[(seed,sign,.1,'lqr')]
        for source in ('raw','compensated'):
            rr=traces[(seed,sign,.1,source)];assert len(rr)==len(base)
            assert all(all(x[k]==y[k] for k in ('command','x','y','heading','actuator')) for x,y in zip(rr,base));exact+=1
    summary={}
    for service in cfg['services_s']:
        summary[str(service)]={}
        for source in cfg['sources']:
            rr=[r for r in rows if float(r['service_s'])==service and r['source']==source]
            summary[str(service)][source]={k:statistics.mean(float(r[k]) for r in rr) for k in ('rmse_m','heading_rmse_rad','rate_rms_rad_s')}
            summary[str(service)][source].update(episodes=len(rr),survived=sum(r['survived']=='True' for r in rr))
    for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((boot7.ROOT/name).read_bytes()).hexdigest()==digest,name
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    result=dict(episodes=len(rows),transitions=ticks,submitted_actor_queries=queries,severe_delay_exact_lqr_pairs=exact,
        original_timestamps_and_unchanged_freshness=True,complete_query_and_controller_replay=True,source_model_hashes_verified=True,
        scope='Narrow known-path development diagnostic; no training, promotion, native/physical confirmation or deadline guarantee')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
