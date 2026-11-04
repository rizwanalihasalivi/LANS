"""Deliberately unreachable 150 m cases: safe stop, NOT recovery successes."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.network import SimulatedChannel,Link
from integrations.connected_v2v.robustness.scenarios import PROFILES,radar_scan
from integrations.unified_lans.physics import advance
from .controller import SettlingFollower
from .geometry import CircularRoad
from .audit import collision,sha


def python_diagnostic(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    road=CircularRoad();ego=np.array([0.,0.,0.,12.,0.,0.]);node=V2VEndpoint('follower')
    head=V2VEndpoint('leader');nodes={'follower':node,'leader':head};control=SettlingFollower(node,road=road,speed=12.)
    channel=SimulatedChannel(9001,default=Link(range_m=150.));rng=np.random.default_rng(9001);trace=[]
    for tick in range(1400):
        now=tick*.05;traffic={'leader':np.array([260.+10*now,0.,0.,10.,0.,0.]),'intruder':np.array([300.+10*now,3.5,0.,10.,0.,0.])}
        node.observe_local(ego,now,now)
        if tick%2==0:
            distance=float(np.linalg.norm(traffic['leader'][:2]-ego[:2]))
            channel.transmit('leader','follower',head.publish(traffic['leader'],now,now),now,distance_m=distance)
            channel.transmit('follower','leader',node.publish(ego,now,now),now,distance_m=distance)
            scan=radar_scan(tick//2,now,ego,traffic,PROFILES['noisy_nonconnected'],rng)
            assert not scan.detections
            control.observe_scan(scan,now)
        events=channel.deliver(now,nodes);assert not events
        command,info=control.decide(now);after=advance(ego,command,.05)
        assert command.accel==-6. and info['sensor_source']=='none' and info['selected_target'] is None
        assert not any(collision(after,z) for z in traffic.values())
        trace.append(dict(time_s=now,before=ego.tolist(),after=after.tolist(),traffic_before={n:z.tolist() for n,z in traffic.items()},
            traffic_after={n:(z+np.array([.5,0,0,0,0,0])).tolist() for n,z in traffic.items()},command=asdict(command),decision=info))
        ego=after
    path=output/'ticks.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in trace))
    assert ego[3]<.1
    result=dict(recovery_passed=False,failsafe_checks_passed=True,classification='OUTSIDE_CONNECTIVITY_ENVELOPE',
        ticks=1400,radio_range_m=150.,out_of_range_drops=channel.dropped['out_of_range'],trace_sha256=sha(path),
        note='No target/path was observable; braking is expected. This is not included as a normal recovery pass.')
    (output/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n');return result


def native_diagnostic(output):
    from .native import run_one
    output=Path(output);raw=run_one((str(output),'unreachable',12.,9001))
    assert 'error' not in raw
    data=[json.loads(s) for s in (output/'follower.jsonl').read_text().splitlines()]
    assert all(z['command']['accel']==-6. and z['decision']['sensor_source']=='none' and z['decision']['selected_target'] is None for z in data)
    assert not raw['passed'] and raw['collisions']==0 and data[-1]['state'][3]<.1
    result=dict(recovery_passed=False,failsafe_checks_passed=True,classification='OUTSIDE_CONNECTIVITY_ENVELOPE',
        radio_range_m=150.,original_recovery_result=raw,note='Expected fail-safe only; ordinary recovery gate remains false.')
    (output/'diagnostic.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--native',action='store_true');a=p.parse_args()
    print(json.dumps(native_diagnostic(a.output) if a.native else python_diagnostic(a.output),indent=2))
