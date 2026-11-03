"""Supplementary development component study; disabled protections are diagnostics."""
from dataclasses import replace, asdict
from functools import partial
from pathlib import Path
import json, math
import numpy as np
from integrations.unified_lans.physics import Config, Command, errors, advance
from integrations.unified_lans.traffic import contact_time, conflict_time, extrapolate
from integrations.unified_lans.inference import load_policy, sha
from integrations.unified_lans.controller import Proposal
from integrations.unified_lans.simulation import move_npcs, truth_metrics
from integrations.unified_lans.run import clean
from tools.unified_campaign import study
from tools.unified_control_v4.control import GRID, StopSupervisor
from .campaign import selected

ROOT=Path(__file__).resolve().parents[2]
VARIANTS=['full','without_ppo','without_adaptation','without_application_prediction',
          'without_traffic_expiry','without_interaction_supervision']


def cases():
    result=[]
    for s,scenario in enumerate(['following','merge','crossing','curved']):
        for replicate in range(4):
            rng=np.random.default_rng(22130000+s*100+replicate)
            fixture=dict(scenario=scenario,mirror=1 if replicate%2==0 else -1,
                speed=float(rng.choice([10.,14.])),stiffness=float(rng.uniform(.8,1.2)),
                lateral=float(rng.uniform(.15,.4))*(1 if replicate%2==0 else -1),
                heading=float(rng.uniform(-.015,.015)),phase=13.,amplitude=1.15,
                traffic_gap=float(rng.uniform(24.,40.)),traffic_speed_offset=float(rng.uniform(-1.,1.)),
                fixture_id=s*4+replicate,replicate=replicate)
            for profile in ['nominal','command_delay','traffic_blackout_brake','ego_blackout']:
                result.append(dict(**fixture,id=len(result),stage='supplementary_development',profile=profile,
                    network='blackout' if profile=='traffic_blackout_brake' else ('ego_blackout' if profile=='ego_blackout' else 'nominal'),
                    delay=.1 if profile=='command_delay' else 0.,network_seed=23130000+s*100+replicate))
    return result


class NoInteraction(StopSupervisor):
    def assess(self,ego,inbox,expected,now,application_s):
        # Explicit component removal in simulation, never a production mode.
        return super().assess(ego,inbox,set(),now,application_s)


def controller_class(base,variant):
    class Ablated(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            if variant=='without_traffic_expiry':
                # Original packet timestamps/ages remain unchanged. Only expiry
                # rejection is removed; growing spatial uncertainty remains.
                self.supervisor=StopSupervisor(replace(self.cfg,traffic_ttl=1e9),self.supervisor.scenario)
            elif variant=='without_interaction_supervision':
                self.supervisor=NoInteraction(self.cfg,self.supervisor.scenario)
        def forecast(self,now):
            if variant=='without_application_prediction':return self.reconstruct(now)
            return super().forecast(now)
    return Ablated


def prepare(root):
    choice,_=selected();root.mkdir(parents=True,exist_ok=False)
    files=[*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'ABLATION_PROTOCOL.md',
           *(ROOT/'tools/unified_control_v4').glob('*.py'),*(ROOT/'tools/unified_control_v5').glob('*.py'),
           *(ROOT/'integrations/unified_lans').glob('*.py'),ROOT/'tools/unified_campaign/study.py']
    protocol=dict(study='supplementary development; not reserved or promotion',
        variants=VARIANTS,cases=cases(),seconds=12.,policy_seed=42,policy_sha256=sha(ROOT/'results/python-campaign-v2/policies/seed-42/policy.zip'),
        config=asdict(Config(horizon=choice['horizon'])),selected_shared_planner=choice,goal_distance_m=60.,
        calibration_sha256=sha(ROOT/'results/proposal-completion-v6/calibration/selection.json'),
        clustered_bootstrap=dict(unit='scenario/traffic fixture, all four communication profiles together',draws=5000,seed=24310001),
        warning_label='independent current-truth constant-velocity geometric hazard proxy, not future actual collision',
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in files})
    (root/'protocol.json').write_text(json.dumps(protocol,indent=2))
    for p in files:
        dest=root/'source'/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
    return protocol


def run_episode(case,variant,model,choice,base):
    cls=controller_class(base,variant)
    def factory(*args,**kwargs):
        args=list(args);args[2]=replace(args[2],horizon=choice['horizon'])
        return cls(*args,penalty=16.,adaptive=variant!='without_adaptation',mpc=True,**kwargs)
    study.Pipeline=factory
    pipe,clock,ego,npcs,network=study.setup(case,'deterministic' if variant=='without_ppo' else 'hybrid',grid=True)
    for name,state in npcs.items():
        if case['scenario']=='crossing':
            state[0]=case['traffic_gap'];state[1]=-case['traffic_gap']*state[3]/case['speed']*case['mirror']
        else:
            state[0]=case['traffic_gap'];state[3]=max(3.,state[3]+case['traffic_speed_offset'])
            if case['scenario'] in ('curved','merge'):
                state[1]=pipe.route.geometry(state[0])[0]
                state[2]=pipe.route.geometry(state[0])[1] if case['scenario']=='curved' else 0.
    rows=[];pending=None;sequence=0
    for tick in range(240):
        now=tick*.05;clock.now=now
        if case['profile']=='traffic_blackout_brake' and now>=2.:
            for state in npcs.values():state[3]=max(0.,state[3]-6.*.05)
        network.emit(now,ego,npcs,pipe.inbox)
        if pending is not None and pending[0]<=now+1e-9:
            pipe.accept(pending[1],now);pending=None
        if variant!='without_ppo' and pending is None:
            features=pipe.features(now)
            if features is not None:
                action,_=model.predict(features,deterministic=True);sequence+=1
                pending=(now+.05,Proposal(sequence,pipe.inbox.latest['ego'].observed_s,now,float(action[0])*.08,now))
        before=ego.copy();npc_before={k:v.copy().tolist() for k,v in npcs.items()}
        _,warning=pipe.supervisor.THRESHOLDS[case['scenario']]
        radius=2*pipe.cfg.vehicle_radius+pipe.cfg.buffer
        truth_ttc=min((min(contact_time(ego,n,radius),conflict_time(ego,n,radius)) for n in npcs.values()),default=math.inf)
        previous=pipe.applied;decision=pipe.decide(now)
        ego=pipe.apply(now,ego,case['stiffness']);move_npcs(npcs,.05,pipe.route,case['scenario'])
        truth=truth_metrics(ego,npcs,pipe.route,pipe.cfg)
        rows.append(dict(tick=tick,time_s=now,state_before=before.tolist(),state_after=ego.tolist(),
            npc_truth_before=npc_before,npc_truth_after={k:v.copy().tolist() for k,v in npcs.items()},
            **truth,**decision,truth_cv_hazard=truth_ttc<=warning,truth_cv_ttc=truth_ttc,
            applied_steering=pipe.applied.steering,applied_accel=pipe.applied.accel,
            steering_rate=(pipe.applied.steering-previous.steering)/.05))
        if truth['collision'] or abs(truth['error'])>2.5:break
    expected=240;n=len(rows)
    warned=[r['risk']!='SAFE' for r in rows];labels=[r['truth_cv_hazard'] for r in rows]
    return dict(case=case,variant=variant,ticks=n,expected_ticks=expected,
        failed=n<expected or any(r['collision'] or r['corridor_exceeded'] for r in rows),
        collision=any(r['collision'] for r in rows),corridor_failure=any(r['corridor_exceeded'] for r in rows),
        rmse_m=math.sqrt((sum(r['error']**2 for r in rows)+(expected-n)*2.5**2)/expected),
        heading_rms=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),
        rate_rms=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),progress_m=float(ego[0]),
        min_clearance=min(r['true_clearance'] for r in rows),
        warning_tp=sum(a and b for a,b in zip(warned,labels)),warning_fp=sum(a and not b for a,b in zip(warned,labels)),
        warning_fn=sum(not a and b for a,b in zip(warned,labels)),
        goal_reached=any(r['x']>=60. for r in rows),
        time_to_goal_s=next((r['time_s']+.05 for r in rows if r['x']>=60.),None),
        jerk_rms=math.sqrt(sum(((rows[i]['applied_accel']-(rows[i-1]['applied_accel'] if i else 0.))/.05)**2 for i in range(n))/n),
        braking_ticks=sum(r['issued_accel']<0 for r in rows),backup_ticks=sum(r['ego_backup'] for r in rows),
        ppo_ticks=sum(r['source']=='ppo' for r in rows)),rows


def audit(record,rows):
    state=np.array(rows[0]['state_before']);previous=Command();pending=[];last_issued=Command();case=record['case']
    route=study.StudyRoute(study.initial(case['scenario'])[0].kind,case['mirror'],case['phase'],case['amplitude'])
    for i,row in enumerate(rows):
        assert i==row['tick'] and i*.05==row['time_s']
        np.testing.assert_allclose(state,row['state_before'],rtol=0,atol=1e-12)
        issued=Command(row['issued_steering'],row['issued_accel'])
        assert abs(issued.steering-last_issued.steering)<=.03+1e-10
        assert abs(issued.steering)<=.5 and -6<=issued.accel<=2.5
        pending.append((row['time_s']+case['delay'],issued));last_issued=issued
        while pending and pending[0][0]<=row['time_s']+1e-9:_,previous=pending.pop(0)
        assert previous==Command(row['applied_steering'],row['applied_accel'])
        state=advance(state,previous,.05,case['stiffness'])
        np.testing.assert_allclose(state,row['state_after'],rtol=0,atol=1e-12)
        error,_=errors(state,route);assert abs(error[0]-row['error'])<1e-12
        if row['source']=='ppo':assert row['proposal_age']<.15 and row['proposal_wall_age']<.15 and not row['ego_backup']
    n=record['expected_ticks']
    value=math.sqrt((sum(r['error']**2 for r in rows)+(n-len(rows))*2.5**2)/n)
    assert abs(value-record['rmse_m'])<1e-12


def main():
    import torch
    torch.set_num_threads(1)
    root=ROOT/'results/proposal-completion-v6/ablations'
    protocol=prepare(root) if not root.exists() else json.loads((root/'protocol.json').read_text())
    for name,h in protocol['source_hashes'].items():assert sha(ROOT/name)==h,('changed source',name)
    assert protocol['calibration_sha256']==sha(ROOT/'results/proposal-completion-v6/calibration/selection.json')
    assert protocol['policy_sha256']==sha(ROOT/'results/python-campaign-v2/policies/seed-42/policy.zip')
    choice,base=selected();model=load_policy(ROOT/'results/python-campaign-v2/policies/seed-42');results=[]
    for case in protocol['cases']:
        for variant in VARIANTS:
            key=f'{case["id"]:03d}-{variant}';meta=root/(key+'.json');raw=root/(key+'.jsonl')
            if meta.exists():
                record=json.loads(meta.read_text());assert record['case']==case and sha(raw)==record['raw_sha256']
                rows=[json.loads(line) for line in raw.read_text().splitlines()]
            else:
                assert not raw.exists(),('preserve interrupted evidence',raw)
                record,rows=run_episode(case,variant,model,choice,base)
                raw.write_text(''.join(json.dumps(clean(r),allow_nan=False)+'\n' for r in rows))
                record['raw_sha256']=sha(raw);record['protocol_sha256']=sha(root/'protocol.json')
                meta.write_text(json.dumps(clean(record),indent=2))
            audit(record,rows);results.append(record)
        print('ABLATION CASE',case['id']+1,'/',len(protocol['cases']),flush=True)
    (root/'summary.json').write_text(json.dumps(clean(results),indent=2))
    (root/'audit.json').write_text(json.dumps(dict(passed=True,episodes=len(results),ticks=sum(r['ticks'] for r in results)),indent=2))


if __name__=='__main__':main()
