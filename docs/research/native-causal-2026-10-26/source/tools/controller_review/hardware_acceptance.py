"""Read-only target-hardware log checks; never sends actuator commands.

A passing log is evidence for that trace, not vehicle safety certification.
Simulated traces are explicitly rejected as hardware evidence.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
from collections import Counter

REQUIRED_SCENARIOS={'nominal','delay20','delay100','cpu_stress','worker_crash'}


def assess(metadata,rows,csv_bytes):
    if metadata.get('trace_kind') not in ('target_hardware','real_vehicle'):
        raise ValueError('physical target-hardware trace required; simulation cannot pass')
    for key in ('device_id','cpu','os','controller_commit','firmware_id','clock_calibration_record'):
        if not metadata.get(key):raise ValueError('missing hardware metadata: '+key)
    if metadata.get('csv_sha256')!=hashlib.sha256(csv_bytes).hexdigest():raise ValueError('CSV hash mismatch')
    if metadata.get('timestamps_same_monotonic_domain') is not True:raise ValueError('clock alignment not established')
    if not 0<=metadata.get('clock_uncertainty_ns',float('inf'))<=1_000_000:raise ValueError('clock uncertainty exceeds1ms')
    if metadata.get('physical_acknowledgements') is not True:raise ValueError('physical acknowledgement evidence required')
    uncertainty=metadata['clock_uncertainty_ns'];seen=set();misses=stale=late=fallback=0
    coverage=Counter()
    ages=[];sensor_ages=[];transport=[];last_seq=-1;last_encoder=None;max_rate=0.;crash_seen=False
    for row in rows:
        scenario=row['scenario'];seen.add(scenario);coverage[scenario]+=1
        seq=int(row['control_sequence']);release=int(row['control_release_ns']);deadline=int(row['control_deadline_ns'])
        command_time=int(row['command_ns']);ack=int(row['ack_ns']);sensor=int(row['current_sensor_ns'])
        encoder=int(row['encoder_ns']);angle=float(row['actuator_angle_rad'])
        weight=float(row['learned_weight']);command=float(row['command_rad']);baseline=float(row['lqr_rad'])
        if not all(math.isfinite(x) for x in (angle,weight,command,baseline)):raise ValueError('nonfinite telemetry')
        if seq<=last_seq or deadline-release!=10_000_000:raise ValueError('invalid control sequence or period')
        if not (sensor<=command_time<=ack and release<=command_time and encoder>=ack):raise ValueError('timestamp ordering invalid')
        if not (0<=weight<=.5 and abs(command)<=.5 and abs(angle)<=.5):raise ValueError('physical bounds exceeded')
        last_seq=seq;miss=ack+uncertainty>deadline;misses+=miss
        if miss and weight>0:late+=1
        sensor_ages.append((ack-sensor+uncertainty)/1e6);transport.append((ack-command_time+uncertainty)/1e6)
        if int(row['packet_sequence'])>=0:
            observation=int(row['packet_observed_ns'])
            request=int(row['request_ns']);entered=int(row['infer_start_ns']);inferred=int(row['infer_end_ns'])
            if not (observation<=request<=entered<=inferred<=command_time):raise ValueError('packet timestamp ordering invalid')
            age=(ack-observation+uncertainty)/1e6;ages.append(age)
            if age>=50 and weight>0:stale+=1
        elif weight>0:raise ValueError('learned authority without a packet')
        unhealthy=row['worker_healthy'] in ('0','False','false')
        crash_seen|=scenario=='worker_crash' and unhealthy
        if (unhealthy and weight!=0) or (weight==0 and abs(command-baseline)>1e-9):fallback+=1
        if last_encoder is not None:
            prev_time,prev_angle=last_encoder
            if encoder<=prev_time:raise ValueError('nonincreasing encoder timestamp')
            rate=abs(angle-prev_angle)/((encoder-prev_time)/1e9);max_rate=max(max_rate,rate)
        last_encoder=(encoder,angle)
    if not rows or not REQUIRED_SCENARIOS.issubset(seen) or not crash_seen or any(coverage[k]<1000 for k in REQUIRED_SCENARIOS):
        raise ValueError('incomplete fault-scenario/worker-crash coverage')
    return dict(trace_checks_pass=misses==stale==late==fallback==0 and max_rate<=.350001,
        samples=len(rows),acknowledged_deadline_misses=misses,stale_authority_violations=stale,
        late_authority_violations=late,worker_fallback_violations=fallback,max_encoder_rate_rad_s=max_rate,
        max_packet_to_ack_ms=max(ages) if ages else None,max_sensor_to_ack_ms=max(sensor_ages),
        max_command_transport_ms=max(transport),vehicle_readiness_certified=False,
        limitation='Metadata/physical provenance require independent verification; this checks one supplied trace only.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metadata',type=Path,required=True)
    p.add_argument('--csv',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        raw=a.csv.read_bytes();rows=list(csv.DictReader(raw.decode().splitlines()))
        result=assess(json.loads(a.metadata.read_text()),rows,raw)
    except (ValueError,KeyError,TypeError) as error:result=dict(trace_checks_pass=False,error=str(error),vehicle_readiness_certified=False)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
    if not result['trace_checks_pass']:raise SystemExit(1)

if __name__=='__main__':main()
