"""Independently check raw timestamps, gate fallback, packets and grid completeness."""
import argparse
import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from realtime_causal import ROOT, load, np, measure, lqr, advance, path_values, configure_lqr, GAINS
from causal_student import REMOVED
from data import G


def verify(folder,model_root=None):
    protocol=json.loads((folder/'protocol.json').read_text())
    report=json.loads((folder/'summary.json').read_text())
    episodes=report['episodes']; expected={(s,c) for s in protocol['seeds'] for c in protocol['cases']}
    assert len(episodes)==len(expected)
    assert {(e['seed'],e['case']) for e in episodes}==expected
    for name,digest in protocol['source_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
    configure_lqr()
    gains=np.array([GAINS[v] for v in (15,20,25)])
    path=tuple(float(v) for v in G['paths']['dlc220'])
    counts=dict(ticks=0,packets=0,stale_ticks=0,deadline_misses=0,active_ticks=0)
    for seed in protocol['seeds']:
        model_folder=(model_root or Path(protocol['model_root']))/str(seed)
        assert hashlib.sha256((model_folder/'student.pt').read_bytes()).hexdigest()==protocol['model_hashes'][str(seed)]
        model=load(model_folder)
        for e in [e for e in episodes if e['seed']==seed]:
            name=f"{seed}-{e['case']}"
            rows=list(csv.DictReader(gzip.open(folder/(name+'-ticks.csv.gz'),'rt')))
            packet_path=folder/(name+'-packets.csv.gz')
            packets=list(csv.DictReader(gzip.open(packet_path,'rt'))) if packet_path.exists() else []
            assert len(rows)==e['ticks']==round(protocol['seconds']/.01)
            assert len(packets)==e['packets']
            assert [int(r['tick']) for r in rows]==list(range(len(rows)))
            issued={int(r['observed_ns']) for r in rows if r['submitted']=='True'}
            packet_map={int(r['seq']):r for r in packets}
            assert len(packet_map)==len(packets)
            for p in packets:
                times=[int(p[k]) for k in ('observed_ns','entered_ns','inferred_ns','sent_ns','received_ns')]
                assert times==sorted(times)
                assert times[0] in issued
                injected=(int(p['sent_ns'])-int(p['inferred_ns']))/1e9
                assert injected+1e-6>=protocol['cases'][e['case']]
                obs=np.asarray(json.loads(p['observation_json']),dtype=np.float32)
                assert np.all(obs[list(REMOVED)]==0)
                action,_=model.predict(obs,deterministic=True)
                assert abs(.08*float(np.clip(action[0],-1,1))-float(p['residual']))<1e-12
            misses=active=stale=0
            noise=np.random.default_rng(protocol['noise_base']+seed).normal(size=(len(rows),4))*np.array([.03,np.deg2rad(.17),.01,.10])
            y,h,_=path_values(0.,path)
            state=np.array([0.,y+.15,h+.01,0.,0.,0.]); shadow=state.copy()
            est=np.zeros(4);cov=np.eye(4)*.01;prev=np.zeros(4)
            se=est.copy();sc=cov.copy();sp=prev.copy();errors=[];shadow_errors=[];differences=[]
            for tick,r in enumerate(rows):
                assert int(r['release_ns'])<=int(r['apply_ns'])
                miss=int(r['apply_ns'])>int(r['target_ns'])+10_000_000
                assert miss==(r['deadline_miss']=='True');misses+=miss
                if miss:assert float(r['weight'])==0 and r['reason']=='deadline'
                command,baseline,weight=map(float,(r['command'],r['baseline'],r['weight']))
                assert abs(command)<=.5 and float(r['actuator_rate'])<=.3500001
                est,cov,prev,v,k=measure(state,20.,path,noise[tick],0,est,cov,prev,tick==0,1.)
                replay_baseline,_=lqr(est,v,k,gains)
                assert abs(replay_baseline-baseline)<1e-12
                state=advance(state,command,20.,1.,1.)
                y,h,_=path_values(state[0],path);error=state[1]-y
                assert abs(error-float(r['error']))<1e-12
                assert abs(state[2]-h-float(r['heading_error']))<1e-12
                errors.append(error)
                se,sc,sp,sv,sk=measure(shadow,20.,path,noise[tick],0,se,sc,sp,tick==0,1.)
                sb,_=lqr(se,sv,sk,gains);shadow=advance(shadow,sb,20.,1.,1.)
                sy,_,_=path_values(shadow[0],path);shadow_errors.append(shadow[1]-sy)
                differences.append(abs(sb-command))
                active+=weight>0
                if r['packet_age_ms']:
                    age=(int(r['apply_ns'])-int(r['packet_observed_ns']))/1e6
                    assert abs(age-float(r['packet_age_ms']))<1e-9
                    assert int(r['packet_seq']) in packet_map
                    held=packet_map[int(r['packet_seq'])]
                    assert int(r['packet_observed_ns'])==int(held['observed_ns'])
                    assert int(held['received_ns'])<=int(r['apply_ns'])
                    if age>=50:
                        stale+=1; assert weight==0 and command==baseline
                    if weight>0:assert 0<=age<50 and r['reason']=='earned'
                else:assert weight==0 and command==baseline
                if r['worker_dead']=='True':assert weight==0 and command==baseline
                if r['reason'] in ('missing','age','age_at_apply','deadline'):assert weight==0 and command==baseline
            assert abs(np.sqrt(np.mean(np.square(errors)))-e['rmse'])<1e-12
            assert abs(np.sqrt(np.mean(np.square(shadow_errors)))-e['paired_lqr_rmse'])<1e-12
            assert abs(max(differences)-e['paired_lqr_max_command_difference'])<1e-12
            assert all(abs(float(r['error']))<=2.5 and abs(float(r['heading_error']))<=.6 for r in rows)==e['survived']
            assert misses==e['deadline_misses'] and active==e['active_ticks'] and stale==e['stale_ticks']
            counts['ticks']+=len(rows);counts['packets']+=len(packets)
            counts['stale_ticks']+=stale;counts['deadline_misses']+=misses;counts['active_ticks']+=active
    result=dict(raw_timestamp_and_model_replay_checks_pass=True,plant_observer_lqr_replay_pass=True,verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),**counts)
    (folder/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--model-root',type=Path);a=p.parse_args();verify(a.run,a.model_root)
