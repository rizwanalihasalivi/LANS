"""Independent scalar RK4/FIFO/metric checks; imports no control or plant code."""
from concurrent.futures import ProcessPoolExecutor
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np


def geometry(x,c):
    x+=c['phase'];kind=c['scenario']
    if kind=='curved':
        w=2*math.pi/120;y=1.5*math.sin(w*x);d=1.5*w*math.cos(w*x)
    elif kind=='merge':
        t=math.tanh((x-30)/12);y=1.75*(1+t);d=1.75*(1-t*t)/12
    else:y=d=0.
    scale=c['mirror']*c['amplitude'];return scale*y,math.atan(scale*d)


def flow(z,u,a,h,stiff):
    def derivative(s):
        _,_,heading,v,vy,r=s;v=max(0.,v)
        if v<2.:dy=-10*vy;dr=10*(v*math.tan(u)/2.6-r)
        else:
            front=80000*stiff*(u-(vy+1.2*r)/v);rear=80000*stiff*(-(vy-1.4*r)/v)
            dy=(front+rear)/1650-v*r;dr=(1.2*front-1.4*rear)/4224
        aa=a if v>0 or a>0 else 0.
        return [v*math.cos(heading)-vy*math.sin(heading),v*math.sin(heading)+vy*math.cos(heading),r,aa,dy,dr]
    z=list(z);steps=max(1,math.ceil(h/.01));dt=h/steps
    for _ in range(steps):
        k1=derivative(z);k2=derivative([x+dt*d/2 for x,d in zip(z,k1)])
        k3=derivative([x+dt*d/2 for x,d in zip(z,k2)]);k4=derivative([x+dt*d for x,d in zip(z,k3)])
        z=[x+dt*(a+2*b+2*c+d)/6 for x,a,b,c,d in zip(z,k1,k2,k3,k4)];z[3]=max(0.,z[3])
    return z


def close(a,b,tol=1e-8):return abs(a-b)<=tol
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def npc_initial(c):
    scenario=c['scenario'];x=30. if scenario=='crossing' else 35. if scenario=='merge' else 42. if scenario=='curved' else 32.
    if scenario=='crossing':y,h,v=-20*c['mirror'],math.pi/2*c['mirror'],8.
    else:y=geometry(x,c)[0] if scenario in ('merge','curved') else 0.;h=geometry(x,c)[1] if scenario=='curved' else 0.;v=max(3.,c['speed']-4.)
    return {dict(following='lead',curved='lead',crossing='cross',merge='merge')[scenario]:
            [x+c.get('npc_x_shift',0.),y,h,v*c.get('npc_speed_scale',1.),0.,0.]}


class Wire:
    """Separate reconstruction of emit, arrival and increasing-sequence acceptance."""
    def __init__(self,c):self.c=c;self.rng=np.random.default_rng(c['network_seed']);self.pending=[];self.latest={}
    def emit(self,i,ego,npcs):
        now=i*.05;profile=self.c['network'];sequence=i+1
        for name,z in [('ego',ego),*npcs.items()]:
            drop=profile=='ego_blackout' and name=='ego' and now>=1.
            if name!='ego':
                drop|=profile=='blackout' and now>=1.
                drop|=profile=='loss' and self.rng.random()<.3
            if drop:continue
            delay=0.
            if name!='ego':
                if profile=='delayed':delay=float(self.rng.choice([.05,.1,.25,.5]))
                elif profile=='reordered':delay=.2 if sequence%2 else 0.
            self.pending.append((now+delay,name,sequence,now,list(z)))
        future=[]
        for due,name,seq,observed,z in self.pending:
            if due>now+1e-9:future.append((due,name,seq,observed,z));continue
            old=self.latest.get(name)
            if old is None or seq>old[0] and observed>=old[1]:self.latest[name]=(seq,observed,z)
        self.pending=future


def episode(job,legacy=False):
    path,c,mode,actor,stage,plan_hash=job;path=Path(path);s=json.loads((path/'summary.json').read_text())
    assert s['case']==c and s['mode']==mode,(path,'metadata')
    if not legacy:assert (s['actor'],s['stage'])==(actor,stage),(path,'actor/stage')
    if plan_hash is not None:assert s['plan_sha256']==plan_hash
    raw=path/'ticks.jsonl';assert sha(raw)==s['raw_sha256']
    rows=[json.loads(x) for x in raw.read_text().splitlines()];assert len(rows)==s['ticks']<=120 and rows
    pending_delay=round(c['delay']/.05);prev=None;issued=applied=0.;errors=[];headings=[];rates=[];collisions=0;corridor=False
    previous_npcs=npc_initial(c);wire=Wire(c)
    initial_y,initial_h=geometry(0.,c)
    initial=[0.,initial_y+c['lateral'],initial_h+c['heading'],c['speed'],0.,0.]
    assert all(close(x,y) for x,y in zip(rows[0]['state_before'],initial)),(path,'initial')
    for i,r in enumerate(rows):
        assert r['tick']==i and close(r['time_s'],i*.05)
        before,after=r['state_before'],r['state_after']
        assert all(math.isfinite(x) for x in [*before,*after,r['issued_steering'],r['issued_accel']])
        if prev is not None:assert all(close(x,y) for x,y in zip(before,prev))
        wire.emit(i,before,previous_npcs)
        assert close(r['ego_age'],i*.05-wire.latest['ego'][1]),(path,i,'ego packet age')
        assert r['ego_backup']==(r['ego_age']>.2+1e-9)
        if r['source']!='hold_brake':
            missing=sorted(n for n in previous_npcs if n not in wire.latest or i*.05-wire.latest[n][1]>.4+1e-9)
            assert sorted(r['missing'])==missing,(path,i,'missing packet')
            ages=[i*.05+c['delay']-wire.latest[n][1] for n in previous_npcs if n not in missing]
            assert close(r['traffic_age'],max(ages,default=0.)),(path,i,'traffic age')
        assert -6<=r['issued_accel']<=2.5 and abs(r['issued_steering'])<=.5+1e-12
        assert abs(r['issued_steering']-issued)<=.03+1e-10;issued=r['issued_steering']
        command=rows[i-pending_delay] if i>=pending_delay else dict(issued_steering=0.,issued_accel=0.)
        assert close(r['applied_steering'],command['issued_steering']) and close(r['applied_accel'],command['issued_accel'])
        predicted=flow(before,r['applied_steering'],r['applied_accel'],.05,c['stiffness'])
        assert all(close(x,y,2e-8) for x,y in zip(predicted,after)),(path.name,i,'RK4')
        y,heading=geometry(after[0],c);err=after[1]-y;ep=math.atan2(math.sin(after[2]-heading),math.cos(after[2]-heading))
        assert close(err,r['error']) and close(ep,r['heading_error'])
        errors.append(err*err);headings.append(ep*ep);rates.append(((r['applied_steering']-applied)/.05)**2);applied=r['applied_steering']
        npc=r['npc_truth'];clear=min(math.hypot(n[0]-after[0],n[1]-after[1])-4.6 for n in npc.values())
        assert close(clear,r['true_clearance']);collisions+=clear<=0;corridor|=abs(err)>1.75
        assert set(npc)==set(previous_npcs)
        for name,n in npc.items():
            old=previous_npcs[name];x=old[0]+old[3]*math.cos(old[2])*.05;yy=old[1]+old[3]*math.sin(old[2])*.05
            hh=old[2]
            if c['scenario']=='curved':yy,hh=geometry(x,c)
            assert close(x,n[0]) and close(yy,n[1]) and close(hh,n[2]) and n[3:]==old[3:],(path,i,'NPC transition')
        if r['source']=='ppo':
            assert r['proposal_age']<.15 and r['proposal_wall_age']<.15 and not r['ego_backup']
        if r.get('planned_candidate_selected') and 'planner_backend' in r:
            assert 0<=r['planner_proposal_age']<.15 and 0<=r['planner_proposal_wall_age']<.15
        if r.get('ego_backup') or r['missing']:assert r['issued_accel']==-6.
        if r.get('recovery') and r['source']=='recovery_lqr':
            chosen=r['recovery']['selected'];assert chosen['physical_margin']>0
            assert chosen['margin']>=0 or r['recovery']['mode']=='uncertified_emergency_improvement'
        if r.get('cbf_status')=='SOLVED':
            assert all(a*r['issued_steering']+b>=-1e-8 for a,b in r['cbf_constraints'])
        previous_npcs=npc;prev=after
    rmse=math.sqrt((math.fsum(errors)+(120-len(rows))*6.25)/120)
    assert close(rmse,s['rmse_m']) and close(math.sqrt(math.fsum(headings)/len(rows)),s['heading_rms'])
    assert close(math.sqrt(math.fsum(rates)/len(rows)),s['rate_rms']) and close(prev[0],s['progress_m'])
    assert collisions==s['collisions'] and bool(len(rows)<120 or collisions or corridor)==s['failed']
    assert close(min(r['true_clearance'] for r in rows),s['min_clearance'])
    assert sum(r['source']=='ppo' for r in rows)==s['ppo_ticks']
    recourse=sum(r['source']=='recovery_lqr' for r in rows)
    uncertified=sum(bool(r.get('recovery') and r['recovery']['mode']=='uncertified_emergency_improvement') for r in rows)
    if not legacy:
        assert recourse==s['recourse_ticks'] and uncertified==s['uncertified_recourse_ticks']
    elif 'recovery_ticks' in s:
        assert recourse==s['recovery_ticks'] and uncertified==s['uncertified_recovery_ticks']
    if len(rows)<120:assert rows[-1]['collision'] or abs(rows[-1]['error'])>2.5
    return dict(case=path.name,passed=True,ticks=len(rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');args=parser.parse_args();root=Path(args.root)
    plan=json.loads((root/'plan.json').read_text());expected=[]
    for stage,cases in plan['cases'].items():
        modes=('lqr','fixed','deterministic','optimized','adaptive','hybrid','v8_common','v8_original','v8_adaptive','cbf') if stage in ('development','final','v8_reserved') else ('lqr','optimized','adaptive','hybrid','v8_original')
        for c in cases:
            for mode in modes:
                for actor in (42,43,44) if mode in ('hybrid','v8_common','v8_original') else (0,):
                    expected.append((root/stage/f'{c["id"]:03d}-{mode}-{actor}',c,mode,actor,stage,sha(root/'plan.json')))
    assert len(expected)==2309 and all((p[0]/'summary.json').exists() for p in expected)
    assert {p[0]/'summary.json' for p in expected}==set(root.glob('*/*/summary.json'))
    for name,h in plan['sources'].items():assert sha(root/'source'/name)==h
    for stage in plan['cases']:
        records=json.loads((root/(stage+'-summary.json')).read_text())
        actual=[json.loads((p[0]/'summary.json').read_text()) for p in expected if p[4]==stage]
        order=lambda r:(r['case']['id'],r['mode'],r['actor'])
        assert sorted(records,key=order)==sorted(actual,key=order)
    with ProcessPoolExecutor(max_workers=4) as pool:results=list(pool.map(episode,expected))
    report=dict(passed=True,episodes=len(results),ticks=sum(r['ticks'] for r in results),
        checks='independent scalar RK4, actual FIFO, physical bounds, regenerated packet arrivals/freshness, initial states, NPC transitions, case coverage and whole-run metrics',
        scope='finite recorded trajectories; not independent native physics or universal safety')
    (root/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
