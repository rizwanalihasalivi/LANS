"""Verify all issued forecast queries and actual completed-response history."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from laptop_full_controller import CausalEnv,controller,observation,advance,np

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run
    count=queries=packets=misses=0
    for seed in (701,802,903):
        folder=out/'runtime'/f'seed-{seed}'
        subprocess.run([sys.executable,str(ROOT/'tools/controller_review/verify_full_laptop.py'),'--run',str(folder),'--models',str(out/'actor')],check=True)
        summary=json.loads((folder/'summary.json').read_text())
        for episode in summary['episodes']:
            rows=list(csv.DictReader((folder/f'{episode["case"]}-ticks.csv').open()))
            f=folder/f'{episode["case"]}-packets.csv';received=list(csv.DictReader(f.open())) if f.exists() else []
            packet_map={int(r['seq']):r for r in received};by_observed={int(r['observed_ns']):r for r in received}
            env=CausalEnv(mode='lqr',case=(20,'dlc220',1,'nominal',episode['noise_id']));env.reset()
            env.estimate=np.zeros(4);env.cov=np.eye(4)*.01;env.previous=np.zeros(4);env.ctrl=controller('delay_compensated');origin=int(rows[0]['target_ns']);last=-1
            for row in rows:
                ctrl=env.ctrl;packet=packet_map.get(int(row['packet_seq']))
                if packet is not None and int(packet['seq'])>last:
                    assert int(row['release_ns'])<=int(packet['received_ns'])<=int(row['release_ns'])+int(row['poll_ns'])
                    ctrl.compensator.observe(int(packet['seq']),(int(packet['received_ns'])-int(packet['observed_ns']))/1e9);last=int(packet['seq']);packets+=1
                env._sense()
                ctrl.packet=None if packet is None else (int(packet['seq']),(int(packet['observed_ns'])-origin)/1e9,float(packet['residual']))
                ctrl.previews=env.obs[6:9].astype(float)*.02
                raw=observation(env.state,env.estimate,env.measured_speed,ctrl.previews,ctrl,(int(row['release_ns'])-origin)/1e9)
                raw[14]=float(np.clip(ctrl.filtered/.08,-1.,1.))
                if row['submitted']=='True':
                    expected,meta=ctrl.prepare_query(raw,env.estimate,env.state[5],env.measured_speed,ctrl.previews,env.gain)
                    np.testing.assert_array_equal(expected,np.array(json.loads(row['query_observation_json']),np.float32))
                    assert meta==json.loads(row['query_metadata_json']);queries+=1
                    reply=by_observed.get(int(row['release_ns']))
                    if reply is not None:
                        np.testing.assert_array_equal(expected,np.array(json.loads(reply['observation_json']),np.float32))
                        assert meta==json.loads(reply['query_metadata_json'])
                command,reason=ctrl.choose((int(row['decision_ns'])-origin)/1e9,env.baseline,env.estimate,env.state[5],env.measured_speed,env.curvature,env.gain)
                for value,key in ((command,'decision_command'),(ctrl.weight,'decision_weight'),(ctrl.filtered,'decision_filter'),(ctrl.good,'decision_good')):assert abs(value-float(row[key]))<1e-11
                if row['deadline_miss']=='True' or (row['packet_age_s'] and float(row['packet_age_s'])>=.05):
                    ctrl.filtered=0.;ctrl.weight=0.;ctrl.good=0;ctrl.last_command=env.baseline;command=env.baseline
                for value,key in ((command,'command'),(ctrl.weight,'weight'),(ctrl.filtered,'filtered_residual'),(ctrl.good,'good')):assert abs(value-float(row[key]))<1e-11
                env.state=advance(env.state,command,20.,.9,1.);env.tick+=1;count+=1;misses+=row['deadline_miss']=='True'
    for name,digest in json.loads((out/'manifest.json').read_text())['hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    result=dict(ticks=count,all_issued_queries_replayed=queries,completed_latency_updates_replayed=packets,deadline_misses=misses,
        predicted_inputs_and_actual_history_verified=True,original_timestamps_and_stale_fallback_verified=True,source_model_hashes_verified=True,
        scope='Short software integration diagnostic, not strict real-time qualification or actual laptop/physical validation')
    (out/'runtime-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(result)

if __name__=='__main__':main()
