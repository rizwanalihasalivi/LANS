"""Independent original-target, recovery/expiry gate and query replay."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'tools/reviewer_v9'))
from runtime9 import CausalEnv,controller,observation,advance,runtime_revoke,np

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--target',action='store_true');p.add_argument('--models',type=Path);a=p.parse_args();out=a.run if a.target else a.run/'timing';protocol=json.loads((out/'protocol.json').read_text());models=a.models or ROOT/protocol['models']
    for name,digest in protocol.get('hashes',{}).items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest()==protocol['model_manifest_sha256']
    count=queries=skipped=0
    for guard in ('on',):
        for seed in protocol['seeds']:
            folder=out/f'seed-{seed}' if a.target else out/guard/f'seed-{seed}'
            subprocess.run([sys.executable,str(ROOT/'tools/reviewer_v9/verify_laptop9.py'),'--run',str(folder),'--models',str(models)],check=True)
            summary=json.loads((folder/'summary.json').read_text())
            for episode in summary['episodes']:
                rows=list(csv.DictReader((folder/f'{episode["case"]}-ticks.csv').open()));f=folder/f'{episode["case"]}-packets.csv'
                received=list(csv.DictReader(f.open())) if f.exists() else [];packets={int(r['seq']):r for r in received};by_observed={int(r['observed_ns']):r for r in received}
                env=CausalEnv(mode='lqr',case=(20,'dlc220',1,'nominal',episode['noise_id']));env.reset();env.estimate=np.zeros(4);env.cov=np.eye(4)*.01;env.previous=np.zeros(4);env.ctrl=controller(protocol['profile']);origin=int(rows[0]['target_ns']);last=-1
                for r in rows:
                    c=env.ctrl;packet=packets.get(int(r['packet_seq']))
                    if packet is not None and int(packet['seq'])>last:
                        if hasattr(c,'compensator'):c.compensator.observe(int(packet['seq']),(int(packet['received_ns'])-int(packet['observed_ns']))/1e9)
                        last=int(packet['seq'])
                    env._sense();c.packet=None if packet is None else (int(packet['seq']),(int(packet['observed_ns'])-origin)/1e9,float(packet['residual']))
                    c.previews=env.obs[6:9].astype(float)*.02
                    raw=observation(env.state,env.estimate,env.measured_speed,c.previews,c,(int(r['release_ns'])-origin)/1e9);raw[14]=float(np.clip(c.filtered/.08,-1.,1.))
                    if r['submitted']=='True':
                        expected=raw
                        if hasattr(c,'compensator'):
                            expected,meta=c.prepare_query(raw,env.estimate,env.state[5],env.measured_speed,c.previews,env.gain)
                            assert meta==json.loads(r['query_metadata_json']);np.testing.assert_array_equal(expected,np.array(json.loads(r['query_observation_json']),np.float32));queries+=1
                        reply=by_observed.get(int(r['release_ns']))
                        if reply is not None:
                            np.testing.assert_array_equal(expected,np.array(json.loads(reply['observation_json']),np.float32))
                            if not hasattr(c,'compensator'):queries+=1
                    decision=int(r['decision_ns']);is_skipped=r['decision_skipped']=='True'
                    assert is_skipped==((guard=='on') and decision>=int(r['target_ns'])+9000000)
                    if is_skipped:command=runtime_revoke(c,env.baseline,'budget');skipped+=1
                    else:command,_=c.choose((decision-origin)/1e9,env.baseline,env.estimate,env.state[5],env.measured_speed,env.curvature,env.gain)
                    for value,key in ((command,'decision_command'),(c.weight,'decision_weight'),(c.filtered,'decision_filter'),(c.good,'decision_good')):assert abs(value-float(r[key]))<1e-11
                    miss=r['deadline_miss']=='True';stale=bool(r['packet_age_s']) and float(r['packet_age_s'])>=.05
                    if miss or stale:command=runtime_revoke(c,env.baseline,'deadline' if miss else 'age_at_apply',clear=miss)
                    for value,key in ((command,'command'),(c.weight,'weight'),(c.filtered,'filtered_residual'),(c.good,'good')):assert abs(value-float(r[key]))<1e-11
                    assert c.last_qualified_sequence==int(r['qualified_sequence'])
                    if r['qualified_time_s']:assert abs(c.last_qualified_time-float(r['qualified_time_s']))<1e-12
                    else:assert c.last_qualified_time is None
                    env.state=advance(env.state,command,20.,.9,1.);env.tick+=1;count+=1
                if episode['case']=='worker_crash':assert episode['external_fault_event'] and any(r['worker_dead']=='True' for r in rows)
    heartbeat=0
    for file in out.glob('heartbeat-*.csv'):
        rr=list(csv.DictReader(file.open()));assert len(rr)==500
        for i,r in enumerate(rr):
            assert int(r['tick'])==i and int(r['deadline_miss'])==(int(r['release_ns'])>int(r['target_ns'])+10000000)
            if i:assert int(r['target_ns'])-int(rr[i-1]['target_ns'])==10000000
        heartbeat+=len(rr)
    result=dict(controller_ticks=count,heartbeat_ticks=heartbeat,query_vectors_verified=queries,budget_decisions_skipped=skipped,original_deadlines_and_gate_physics_verified=True,
        query_scope='All issued causal-state compensated vectors, all metadata, and every returned actor vector; expiry/recovery states replayed tick by tick.',source_model_hashes_verified=True)
    (out/'full-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
