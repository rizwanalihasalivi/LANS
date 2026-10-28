"""Independent SIL plant/observer/LQR and original timestamp/actor replay."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime9 import CausalEnv,controller,load_portable,advance,path_values,np,CASES


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--models',type=Path,required=True)
    args=p.parse_args();report=json.loads((args.run/'summary.json').read_text());actor=load_portable(args.models);actor.golden_check()
    declared=json.loads((args.models/'manifest.json').read_text()).get('profile')
    compensated_profile=declared=='causal_recovery_history_v9'
    history_profile=declared=='causal_recovery_history_v9'
    removed=[16,17]
    count=packets_count=0
    assert {r['case'] for r in report['episodes']}==set(CASES)
    for e in report['episodes']:
        assert (e['profile']=='history_comp')==history_profile
        assert (e['profile']=='history_comp')==compensated_profile
        name=e['case'];ticks=list(csv.DictReader((args.run/f'{name}-ticks.csv').open()))
        file=args.run/f'{name}-packets.csv';packets=list(csv.DictReader(file.open())) if file.exists() else []
        issued={int(r['release_ns']):r for r in ticks if r.get('submitted','True')=='True'};packet_map={int(r['seq']):r for r in packets}
        queries_by_observed={int(r['observed_ns']):r for r in packets}
        assert len(packet_map)==len(packets)==e['actor_packets']
        for r in packets:
            times=[int(r[k]) for k in ('observed_ns','entered_ns','inferred_ns','sent_ns','received_ns')]
            assert times==sorted(times) and times[0] in issued
            assert times[3]-times[2]>=round(CASES[name]*1e9)
            x=np.array(json.loads(r['observation_json']),np.float32)
            assert x.shape==(20,) and np.isfinite(x).all() and np.all(x[removed]==0)
            residual=[-.08,-.04,0.,.04,.08][actor.logits(actor.load(e['seed']),x[None,:]).argmax(1)[0]]
            assert abs(residual-float(r['residual']))<1e-12
        env=CausalEnv(mode='lqr',case=(20,'dlc220',1,'nominal',e['noise_id']));env.reset()
        env.estimate=np.zeros(4);env.cov=np.eye(4)*.01;env.previous=np.zeros(4);env.ctrl=controller(e['profile'])
        misses=0;active=0;previous_filter=0.
        for i,r in enumerate(ticks):
            assert int(r['tick'])==i and int(r['release_ns'])<=int(r['apply_ns'])
            if i:assert int(r['target_ns'])==int(ticks[i-1]['target_ns'])+10000000
            miss=int(r['apply_ns'])>int(r['target_ns'])+10000000;assert miss==(r['deadline_miss']=='True');misses+=miss
            env._sense();command=float(r['command']);weight=float(r['weight']);baseline=float(r['baseline'])
            assert abs(env.baseline-baseline)<1e-12
            if int(r['release_ns']) in queries_by_observed:
                query=np.array(json.loads(queries_by_observed[int(r['release_ns'])]['observation_json']),np.float32)
                physical=query
                if compensated_profile:
                    physical=np.array(json.loads(queries_by_observed[int(r['release_ns'])]['query_metadata_json'])['raw_observation'],np.float32)
                np.testing.assert_array_equal(physical[:9],env.obs[:9])
                if history_profile:assert query[14]==np.float32(np.clip(previous_filter/.08,-1.,1.))
            assert abs(command-max(-.5,min(.5,baseline+weight*float(r['filtered_residual']))))<1e-12
            seq=int(r['packet_seq'])
            if seq>=0:
                held=packet_map[seq];assert int(held['received_ns'])<=int(r['apply_ns'])
                age=(int(r['apply_ns'])-int(held['observed_ns']))/1e9
                assert abs(age-float(r['packet_age_s']))<1e-12
            else:age=None;assert weight==0
            if miss or r['worker_dead']=='True' or (age is not None and age>=.05):assert weight==0 and command==baseline
            if weight:assert age is not None and 0<=age<.05
            active+=abs(command-baseline)>1e-10
            old=env.state[5];env.state=advance(env.state,command,20.,.9,1.);env.tick+=1
            previous_filter=float(r['filtered_residual'])
            y,h,_=path_values(env.state[0],env.path)
            for a,b in ((env.state[1]-y,float(r['error'])),(env.state[2]-h,float(r['heading_error'])),
                        (env.state[5],float(r['actuator'])),((env.state[5]-old)/.01,float(r['actuator_rate']))):assert abs(a-b)<1e-12
        assert misses==e['deadline_misses'] and active==e['nonzero_correction_ticks'];count+=len(ticks);packets_count+=len(packets)
    result=dict(ticks=count,packets=packets_count,original_deadlines_verified=True,actor_and_removed_channels_verified=True,
                plant_observer_lqr_replay_verified=True,query_physical_features_replayed=True,fallback_verified=True,target_platform_validation=False)
    (args.run/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
