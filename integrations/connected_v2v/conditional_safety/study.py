"""New staged, source-frozen exact longitudinal reference simulations."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import heapq
import itertools
import json
from pathlib import Path
import random
import shutil
import traceback
from .shield import Contract,SafetyShield,envelope
from .audit import check_episode,audit
from .prove import run as prove

ROOT=Path(__file__).resolve().parents[3]
PROFILES=('steady_connected','leader_emergency','v2v_blackout','dual_blackout',
    'bounded_sensor_error','admissible_cutin','adversarial_nominal','permanent_blackout')
SPEEDS=(8,12,16)
DEV=(4001,4003,4007)
VAL=(5003,5009,5011,5021,5023,5039,5051,5059,5077,5081)


def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def text_state(z):return [str(x) for x in z]


def message(name,source,sequence,now,state,rng):
    error=150 if source=='radar' else 100
    return dict(name=name,source=source,sequence=sequence,observed=str(now),
        position=str(state[0]+F(rng.randint(-error,error),1000)),
        speed=str(state[1]+F(rng.randint(-80,80),1000)))


def run_episode(path,profile,speed,seed):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    c=Contract();h=c.horizon;seconds=F(40)
    rng=random.Random(seed);sensor=random.Random(seed+100000);radio=random.Random(seed+200000)
    x,v=F(0),F(speed)
    shield=SafetyShield(x+F('.05'),v+F('.05'),contract=c)
    gap=c.margin+(v+F('.05'))**2/(2*c.brake)+40+F(rng.randint(0,20),10)
    obstacles={'leader':(gap,v)}
    latest={};queue=[];serial=0;rows=[]
    write(path/'case.json',dict(profile=profile,speed=speed,seed=seed,seconds=str(seconds),
        contract={k:str(v) for k,v in asdict(c).items()},initial_upper=[str(shield.x),str(shield.v)]))
    for tick in range(int(seconds/h)):
        now=tick*h
        admitted=[]
        if profile=='admissible_cutin' and tick==120:
            # Scenario state is fixed from initial parameters, not a controller
            # target command. The theorem still requires admissible observation
            # at the entry boundary; arbitrary hidden lane entry is excluded.
            obstacles['cutin']=(gap-15+F(speed)*now,F(speed)-2)
            admitted.append('cutin')
        arrivals=[]
        for name,state in obstacles.items():
            if tick%2:continue
            for source in ('radar','v2v'):
                blackout=(source=='v2v' and profile in ('v2v_blackout','dual_blackout') and 8<=now<14
                    or profile=='dual_blackout' and source=='radar' and 8<=now<14
                    or profile=='permanent_blackout' and now>=8)
                distance=state[0]-x
                available=distance <= (120 if source=='radar' else 150)
                if tick!=0 and name not in admitted and (blackout or not available or radio.random()<.1):continue
                msg=message(name,source,tick//2,now,state,sensor)
                serial+=1
                delay=0 if tick==0 or name in admitted else radio.choice((1,2))
                heapq.heappush(queue,(tick+delay,serial,msg))
                if tick and radio.random()<.1:
                    serial+=1;heapq.heappush(queue,(tick+delay+3,serial,msg))
                if tick and tick%40==0:
                    serial+=1;heapq.heappush(queue,(tick+12,serial,msg))
        while queue and queue[0][0]<=tick:
            _,_,msg=heapq.heappop(queue);source=msg['source']
            error=F('.15') if source=='radar' else F('.10')
            ttl=F('.2') if source=='radar' else F('.4')
            accepted=shield.observe(msg['name'],source,msg['sequence'],F(msg['observed']),now,F(msg['position'])-error,ttl)
            arrivals.append(dict(message=msg,accepted=accepted))
            if accepted:latest[(msg['name'],source)]=msg
        measured_x=x+F(sensor.randint(-50,50),1000)
        measured_v=v+F(sensor.randint(-50,50),1000)
        shield.refine_ego(measured_x+F('.05'),max(F(0),measured_v+F('.05')))
        fresh=[msg for (name,source),msg in latest.items() if now-F(msg['observed']) <= (F('.2') if source=='radar' else F('.4'))]
        if profile=='adversarial_nominal':nominal=c.maximum_command
        elif not fresh:nominal=c.emergency
        else:
            target=min(fresh,key=lambda z:F(z['position']))
            vv=max(F(0),measured_v)
            nominal=min(F('.64')*(F(target['position'])-measured_x-6-F('1.2')*vv)
                +F('.832')*(max(F(0),F(target['speed']))-vv),F('.8')*(F(speed)-vv))
        command,certificate=shield.choose(nominal)
        actual=command+F(rng.randint(-250,250),1000)
        ds,after_v=envelope(v,actual,h);after=(x+ds,after_v)
        obstacle_accels={name:F(0) for name in obstacles}
        if profile in ('leader_emergency','dual_blackout','adversarial_nominal') and now>=9:
            obstacle_accels['leader']=F(-8)
        elif profile=='bounded_sensor_error' and 10<=now<12:
            obstacle_accels['leader']=F(-2)
        after_obstacles={}
        for name,(p,w) in obstacles.items():
            displacement,speed_after=envelope(w,obstacle_accels[name],h)
            after_obstacles[name]=(p+displacement,speed_after)
        rows.append(dict(tick=tick,time=str(now),ego_before=text_state((x,v)),ego_after=text_state(after),
            ego_measurement=text_state((measured_x,measured_v)),
            obstacles_before={n:text_state(z) for n,z in obstacles.items()},
            obstacles_after={n:text_state(z) for n,z in after_obstacles.items()},
            obstacle_accels={n:str(a) for n,a in obstacle_accels.items()},admissions=admitted,
            arrivals=arrivals,nominal=str(nominal),command=str(command),actual_accel=str(actual),certificate=certificate))
        x,v=after;obstacles=after_obstacles
    (path/'ticks.jsonl').write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
    result=check_episode(path);result.update(profile=profile,speed=speed,seed=seed)
    write(path/'summary.json',result)
    return result


def task(args):
    path,*case=args
    try:return run_episode(path,*case)
    except Exception:
        path=Path(path);path.mkdir(parents=True,exist_ok=True);(path/'failure.txt').write_text(traceback.format_exc())
        return dict(passed=False,profile=case[0],speed=case[1],seed=case[2],error='failure.txt')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--stage',choices=('development','validation'),required=True);a=p.parse_args()
    root=Path(a.output).resolve()
    if a.stage=='development':
        root.mkdir(parents=True,exist_ok=False)
        files=sorted(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name(n) for n in ('THEOREM.md','PROTOCOL.md','requirements-proof.txt')]
        sources={str(z.relative_to(ROOT)):sha(z) for z in files}
        for name in sources:
            dest=root/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
        write(root/'plan.json',dict(profiles=PROFILES,speeds=SPEEDS,development_seeds=DEV,validation_seeds=VAL,sources=sources))
        prove(root/'proof')
    plan=json.loads((root/'plan.json').read_text())
    for name,digest in plan['sources'].items():assert sha(ROOT/name)==digest,'source freeze changed'
    if a.stage=='validation':
        assert json.loads((root/'development/summary.json').read_text())['passed']
        assert audit(root,'development')['development']['passed']
        assert json.loads((root/'boundary.json').read_text())['passed']
        assert json.loads((root/'proof/proof.json').read_text())['passed']
    stage=root/a.stage;stage.mkdir(exist_ok=False)
    jobs=[(str(stage/f'{profile}-{speed}-{seed}'),profile,speed,seed)
        for profile,speed,seed in itertools.product(PROFILES,SPEEDS,DEV if a.stage=='development' else VAL)]
    results=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(task,j) for j in jobs]):
            result=future.result();results.append(result);print(json.dumps(result),flush=True)
    results.sort(key=lambda r:(r['profile'],r['speed'],r['seed']))
    for name,digest in plan['sources'].items():assert sha(ROOT/name)==digest,'source freeze changed'
    write(stage/'summary.json',dict(passed=all(z['passed'] for z in results),results=results))
    if not all(z['passed'] for z in results):raise SystemExit('cohort gate failed; evidence preserved')


if __name__=='__main__':main()
