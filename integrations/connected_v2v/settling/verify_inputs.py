"""Regenerate local/cooperative inputs from independently audited stored traffic.

The sensor model is shared, not claimed as an independent perception-physics
implementation. No controller is instantiated and no action selects expected data.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import zlib
import numpy as np
from integrations.connected_v2v.robustness.scenarios import Profile,radar_scan
from integrations.connected_v2v.robustness.perception import encode_peer_scan,decode_peer_scan
from integrations.connected_v2v.autonomy.study import decode_scan
from integrations.connected_v2v.node import V2VEndpoint
from integrations.connected_v2v.network import Link,SimulatedChannel
from integrations.connected_v2v.messages import decode_beacon
from integrations.connected_v2v.autonomy.road import Road
from .relay import FormationRelays


def check(path):
    path=Path(path);spec=json.loads((path/'case.json').read_text());p=Profile(**spec['profile'])
    data=[json.loads(l) for l in (path/'ticks.jsonl').read_text().splitlines()]
    connected=[n for n in data[0]['traffic_before'] if not(p.nonconnected and n in ('intruder','adjacent-0','adjacent-2','adjacent-4'))]
    sensors=np.random.default_rng(np.random.SeedSequence([spec['seed'],11]))
    latencies=np.random.default_rng(np.random.SeedSequence([spec['seed'],13]))
    peers={n:np.random.default_rng(np.random.SeedSequence([spec['seed'],41,zlib.crc32(n.encode())])) for n in connected}
    local={};cooperative={};local_count=peer_count=radio_count=0
    nodes={n:V2VEndpoint(n) for n in connected};nodes['follower']=V2VEndpoint('follower')
    pending={n:FormationRelays() for n in nodes};road=Road(p.radius)
    channel=SimulatedChannel(spec['seed']+23,default=Link(delay_s=.05,jitter_s=.025,loss=.1,duplicate=.1,range_m=150.,blackout=((11.,12.5),) if p.radio_blackout else ()))
    for row in data:
        now=row['time_s'];tick=row['tick'];ego=np.array(row['before']);traffic={n:np.array(z) for n,z in row['traffic_before'].items()}
        nodes['follower'].observe_local(ego,now,now)
        if tick%2==0:
            positions={**traffic,'follower':ego}
            for name,sender in nodes.items():
                own=sender.publish(positions[name],now,now);relay=pending[name].take(now,road)
                for raw in [own]+([relay] if relay is not None else []):
                    origin=decode_beacon(raw).vehicle_id
                    for receiver in nodes:
                        if receiver in (name,origin):continue
                        channel.transmit(origin,receiver,raw,now,distance_m=float(np.linalg.norm(positions[name][:2]-positions[receiver][:2])))
            if not(p.radar_blackout and 11.<=now<12.5):
                scan=radar_scan(tick//2,now,ego,traffic,p,sensors)
                due=now+p.latency+float(latencies.uniform(-p.latency_jitter,p.latency_jitter))
                local[scan.sequence]=(scan,due)
            if not(p.radio_blackout and 11.<=now<12.5):
                for name in connected:
                    if np.linalg.norm(traffic[name][:2]-ego[:2])>150.:continue
                    others={**traffic,'follower':ego};others.pop(name)
                    scan=radar_scan(tick//2,now,traffic[name],others,p,peers[name])
                    cooperative[name,scan.sequence]=encode_peer_scan(name,scan)
        delivered=channel.deliver(now,nodes)
        assert delivered==row['radio'],'range/loss/delay/relay delivery regeneration mismatch'
        radio_count+=len(delivered)
        for event in delivered:
            if event['accepted']:pending[event['receiver']].add(event['message'].encode())
        for event in row['radar']:
            scan=decode_scan(event['scan']);expected,due=local.pop(scan.sequence)
            assert scan==expected and now-.05-1e-8<due<=now+1e-8
            local_count+=1
        assert all(due>now+1e-9 for _,due in local.values())
        for event in row['peer_scans']:
            raw=event['message'].encode();name,scan=decode_peer_scan(raw)
            assert raw==cooperative.pop((name,scan.sequence))
            assert abs(now-scan.observed_s-.05)<1e-8
            peer_count+=1
    assert not cooperative
    # Local samples generated at the final tick may have delivery beyond70 s.
    assert all(due>data[-1]['time_s'] for _,due in local.values())
    return local_count,peer_count,radio_count


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--stage',choices=('development','validation'),required=True);a=p.parse_args()
    root=Path(a.root)/a.stage;summary=json.loads((root/'summary.json').read_text())
    paths=[str(root/f"{r['case']}-{r['speed']:g}-{r['seed']}") for r in summary['results']]
    with ProcessPoolExecutor(max_workers=3) as pool:checked=list(pool.map(check,paths))
    print(json.dumps(dict(passed=True,episodes=len(paths),local_scans=sum(z[0] for z in checked),cooperative_datagrams=sum(z[1] for z in checked),regenerated_radio_deliveries=sum(z[2] for z in checked)),indent=2))
