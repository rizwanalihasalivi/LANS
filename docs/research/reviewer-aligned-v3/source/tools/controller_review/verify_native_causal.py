"""Audit native simulator telemetry and actual causal-worker model outputs."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/controller_review'))
from causal_student import load_causal,REMOVED,np


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--models',type=Path,required=True);p.add_argument('--source-root',type=Path,default=ROOT);a=p.parse_args()
    protocol=json.loads((a.run/'protocol.json').read_text())
    for rel,digest in protocol['source_hashes'].items():assert hashlib.sha256((a.source_root/rel).read_bytes()).hexdigest()==digest,rel
    for rel,digest in protocol['model_hashes'].items():assert hashlib.sha256((a.models/'701'/rel).read_bytes()).hexdigest()==digest
    summaries=json.loads((a.run/'summary.json').read_text());results=[]
    for metrics in summaries:
        case=metrics['case'];name=Path(case['output']).name;folder=a.run/name
        provenance=json.loads((folder/'provenance.json').read_text())
        assert hashlib.sha256((folder/'telemetry.csv').read_bytes()).hexdigest()==provenance['telemetry_sha256']
        rows=list(csv.DictReader((folder/'telemetry.csv').open()))
        frame=None
        if (folder/'map-frame.json').exists():
            frame=json.loads((folder/'map-frame.json').read_text())
        assert len(rows)==metrics['steps']
        if metrics['survived']:assert len(rows)==metrics['scheduled_steps']
        else:assert metrics['failure']=='tracking_envelope'
        assert metrics['worker_failed'] is None
        packets=json.loads((folder/'packets.json').read_text()) if (folder/'packets.json').exists() else []
        mapping={int(p['seq']):p for p in packets};assert len(mapping)==len(packets)
        if case['mode']=='causal_student':
            assert packets,'native worker produced no packets'
            model=load_causal(a.models/'701')
            for packet in packets:
                assert packet['observed_ns']<=packet['entered_ns']<=packet['inferred_ns']<=packet['sent_ns']<=packet['received_ns']
                assert (packet['sent_ns']-packet['inferred_ns'])/1e9+1e-6>=case['delay_ms']/1000
                obs=np.asarray(json.loads(packet['observation_json']),dtype=np.float32)
                assert obs.shape==(20,) and np.all(obs[list(REMOVED)]==0)
                action,_=model.predict(obs,deterministic=True)
                assert abs(.08*float(np.clip(action[0],-1,1))-packet['residual'])<1e-12
        misses=active=stale=0;errors=[];phys=[]
        for i,row in enumerate(rows):
            assert int(row['step'])==i+1
            command=float(row['command_rad']);baseline=float(row['lqr_command_rad']);weight=float(row['ppo_weight'])
            if frame is not None:
                dx=float(row['world_x_cg_m'])-frame['world_origin_cg_m'][0]
                dy=float(row['world_y_cg_m'])-frame['world_origin_cg_m'][1]
                c=np.cos(frame['rotation_rad']);sn=np.sin(frame['rotation_rad'])
                assert abs(c*dx-sn*dy-float(row['x_cg_m']))<1e-9
                assert abs(sn*dx+c*dy+frame['map_y_offset_m']-float(row['y_cg_m']))<1e-9
                assert abs(float(row['world_heading_rad'])+frame['rotation_rad']-float(row['heading_rad']))<1e-10
            assert abs(command)<=.5 and abs(float(row['actuator_rate_rad_s']))<=.35000001
            error=float(row['y_cg_m'])-float(row['reference_y_m']);errors.append(error)
            assert abs(error-float(row['error_m']))<1e-12
            inside=abs(error)<=2.5 and abs(float(row['heading_error_rad']))<=.6
            if metrics['survived'] or i<len(rows)-1:assert inside
            else:assert not inside
            if i:assert abs(float(row['t_command_s'])-float(rows[i-1]['t_command_s'])-.01)<1e-7
            miss=int(row['deadline_miss']);misses+=miss;active+=weight>0
            if 'wall_deadline_ns' in row:
                assert miss==int(int(row['wall_apply_ns'])>int(row['wall_deadline_ns']))
                assert abs(float(row['wall_response_ms'])-(int(row['wall_apply_ns'])-int(row['wall_deadline_ns'])+10_000_000)/1e6)<1e-8
            assert abs(float(row['control_wall_ms'])-(int(row['wall_apply_ns'])-int(row['wall_release_ns']))/1e6)<1e-8
            seq=int(row['output_sequence'])
            if seq:
                packet=mapping[seq]
                assert int(row['packet_observed_wall_ns'])==packet['observed_ns']
                assert abs(float(row['t_observation_s'])-packet['observed_sim_s'])<1e-12
                sim_age=float(row['t_command_s'])-packet['observed_sim_s']
                wall_age=(int(row['wall_apply_ns'])-packet['observed_ns'])/1e9
                effective=max(sim_age,wall_age)
                assert abs(float(row['effective_action_age_s'])-effective)<1e-8
                if effective>=.05:
                    stale+=1;assert weight==0 and command==baseline
            else:assert weight==0
            if miss:assert weight==0 and command==baseline
            if weight==0:assert command==baseline
            if case['delay_ms']>=50:assert weight==0 and command==baseline
            phys.append({key:row[key] for key in ('command_rad','actuator_rad','x_cg_m','y_cg_m','heading_rad','error_m')})
        assert misses==metrics['native_deadline_misses']
        assert abs(np.sqrt(np.mean(np.square(errors)))-metrics['rmse_m'])<1e-12
        results.append(dict(name=name,mode=case['mode'],path=case['path'],speed=case['speed'],delay_ms=case['delay_ms'],
            survived=metrics['survived'],ticks=len(rows),packets=len(packets),deadline_misses=misses,active_ticks=active,
            stale_ticks=stale,rmse_m=metrics['rmse_m'],physical=phys))
    # Severe-delay equality is an independent physical/control trace comparison.
    severe=[]
    for r in results:
        if r['mode']=='causal_student' and r['delay_ms']>=50:
            baseline=next(b for b in results if b['mode']=='lqr' and b['speed']==r['speed'] and b['path']==r['path'])
            diff=max(abs(float(x[k])-float(y[k])) for x,y in zip(r['physical'],baseline['physical']) for k in x)
            severe.append(dict(name=r['name'],max_physical_difference=diff,exact_match=diff==0))
    for r in results:r.pop('physical')
    result=dict(native_contract_checks_pass=True,native_interface_verification_pass=all(m['survived'] for m in summaries),smoke=protocol['smoke'],cases=results,
        severe_delay_pair_comparisons=severe,strict_native_wall_timing_pass=all(r['deadline_misses']==0 for r in results))
    (a.run/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
