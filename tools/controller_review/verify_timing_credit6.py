import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(Path(__file__).resolve().parent))
from laptop_full_controller import CausalEnv,controller,observation,advance,np


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();out=args.run
    protocol=json.loads((out/'protocol.json').read_text());models=ROOT/protocol['models']
    for name,digest in protocol['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest()==protocol['actor_manifest_sha256']
    ticks=0
    for profile in protocol['profiles']:
        for seed in protocol['seeds']:
            folder=out/profile/f'seed-{seed}'
            subprocess.run([sys.executable,str(ROOT/'tools/controller_review/verify_full_laptop.py'),'--run',str(folder),'--models',str(models)],check=True)
            episodes=json.loads((folder/'summary.json').read_text())['episodes']
            for e in episodes:
                rows=list(csv.DictReader((folder/f'{e["case"]}-ticks.csv').open()));file=folder/f'{e["case"]}-packets.csv'
                packets=list(csv.DictReader(file.open())) if file.exists() else [];packet_map={int(r['seq']):r for r in packets}
                queries={int(r['observed_ns']):r for r in packets}
                env=CausalEnv(mode='lqr',case=(20,'dlc220',1,'nominal',e['noise_id']));env.reset()
                env.estimate=np.zeros(4);env.cov=np.eye(4)*.01;env.previous=np.zeros(4);env.ctrl=controller(profile);origin=int(rows[0]['target_ns'])
                for r in rows:
                    env._sense();ctrl=env.ctrl
                    packet=packet_map.get(int(r['packet_seq']));ctrl.packet=None if packet is None else (int(packet['seq']),(int(packet['observed_ns'])-origin)/1e9,float(packet['residual']))
                    ctrl.previews=env.obs[6:9].astype(float)*.02
                    expected=observation(env.state,env.estimate,env.measured_speed,ctrl.previews,ctrl,(int(r['release_ns'])-origin)/1e9)
                    if getattr(ctrl,'policy_history_feature',False):expected[14]=float(np.clip(ctrl.filtered/.08,-1.,1.))
                    if int(r['release_ns']) in queries:np.testing.assert_array_equal(expected,np.array(json.loads(queries[int(r['release_ns'])]['observation_json']),np.float32))
                    command,reason=ctrl.choose((int(r['decision_ns'])-origin)/1e9,env.baseline,env.estimate,env.state[5],env.measured_speed,env.curvature,env.gain)
                    for actual,key in ((command,'decision_command'),(ctrl.weight,'decision_weight'),(ctrl.filtered,'decision_filter'),(ctrl.good,'decision_good')):
                        assert abs(actual-float(r[key]))<1e-11,(e['case'],r['tick'],key)
                    if r['deadline_miss']=='True' or (r['packet_age_s'] and float(r['packet_age_s'])>=.05):
                        ctrl.filtered=0.;ctrl.weight=0.;ctrl.good=0;ctrl.last_command=env.baseline;command=env.baseline
                    for actual,key in ((command,'command'),(ctrl.weight,'weight'),(ctrl.filtered,'filtered_residual'),(ctrl.good,'good')):assert abs(actual-float(r[key]))<1e-11
                    env.state=advance(env.state,command,20.,.9,1.);env.tick+=1;ticks+=1
                if e['case']=='worker_crash':
                    assert e['external_fault_event'] and 'error' not in e['external_fault_event']
                    assert any(r['worker_dead']=='True' for r in rows)
    heartbeat=0
    for f in out.glob('heartbeat-*.csv'):
        rows=list(csv.DictReader(f.open()));assert len(rows)==500
        for i,r in enumerate(rows):
            assert int(r['tick'])==i
            if i:assert int(r['target_ns'])-int(rows[i-1]['target_ns'])==10000000
            assert int(r['deadline_miss'])==(int(r['release_ns'])>int(r['target_ns'])+10000000)
        heartbeat+=len(rows)
    (out/'verification.json').write_text(json.dumps(dict(ticks=ticks,heartbeat_ticks=heartbeat,full_causal_query_gate_and_physical_replay=True,
        original_deadlines_verified=True,independent_fault_injection_verified=True,source_and_model_hashes_verified=True),indent=2)+'\n')
    print('Verified',ticks,'controller ticks and',heartbeat,'heartbeat ticks')


if __name__=='__main__':main()
