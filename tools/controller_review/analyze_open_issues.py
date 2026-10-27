"""Descriptive old-data audit plus an explicit policy-state alias counterexample."""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools/reviewer_v4'))
import boot4
import numpy as np
from interface4 import FreshController
from environment import CausalEnv
from supervisor import observation
from kernels import lqr


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    source=ROOT/'docs/research/reviewer-aligned-v3';result=dict(scope='Post-hoc descriptive diagnosis of inspected development/software-smoke data; no new selection or reserved data')
    cases=[]
    for file in (source/'kit-smoke').glob('*-ticks.csv'):
        rows=list(csv.DictReader(file.open()));missed=[r for r in rows if r['deadline_miss']=='True']
        packetfile=file.with_name(file.name.replace('-ticks','-packets'));packets=list(csv.DictReader(packetfile.open())) if packetfile.exists() else []
        ages=[float(r['packet_age_s'])*1000 for r in rows if r['packet_age_s']]
        inference=[(int(r['inferred_ns'])-int(r['entered_ns']))/1e6 for r in packets]
        cases.append(dict(case=file.stem.removesuffix('-ticks'),ticks=len(rows),missed=len(missed),
            already_late_at_release=sum(int(r['release_lateness_ns'])>=10000000 for r in missed),
            wall_control_over10ms=sum(int(r['control_ns'])>=10000000 for r in missed),
            median_packet_age_ms=statistics.median(ages) if ages else None,
            median_actual_inference_ms=statistics.median(inference) if inference else None,
            active_ticks=sum(float(r['weight'])>0 for r in rows),nonzero_correction_ticks=sum(abs(float(r['command'])-float(r['baseline']))>1e-10 for r in rows)))
    result['old_kit_cases']=cases
    result['age_gain']={str(ms):dict(cap=.25*math.exp(-.8*max(0,ms-5)),fraction_of_nominal_cap=math.exp(-.8*max(0,ms-5))) for ms in (0,5,10,20,30,40)}
    episodes=list(csv.DictReader((source/'episodes.csv').open()));strata=[]
    for scenario in ('nominal','tire','delay20','delay100'):
        rr=[r for r in episodes if r['scenario']==scenario]
        groups={name:[r for r in rr if r['source']==name] for name in ('lqr','student','ppo')}
        means={name:statistics.mean(float(r['rmse_m']) for r in group) for name,group in groups.items()}
        strata.append(dict(scenario=scenario,**means,ppo_gain_vs_student_pct=100*(1-means['ppo']/means['student'])))
    result['old_v3_strata']=strata
    env=CausalEnv(case=(20,'dlc220',1,'nominal',1376000999));env.reset();rng=np.random.default_rng(4733);alias=None
    for _ in range(2000):
        z=rng.normal(size=4)*[.3,.1,.03,.1];speed=20.;ks=rng.normal(size=3)*.002;act=float(rng.uniform(-.08,.08))
        baseline,gain=lqr(z,speed,float(ks[0]),env.gains);state=np.zeros(6);state[5]=act
        a,b=FreshController(),FreshController()
        for c,f in ((a,-.06),(b,.06)):
            c.packet=(7,0.,-.04);c.last_sequence=7;c.good=2;c.weight=0.;c.last_command=float(baseline);c.previews=ks.copy();c.filtered=f
        x=observation(state,z,speed,ks,a,.01);y=observation(state,z,speed,ks,b,.01);assert np.array_equal(x,y)
        ca,ra=a.choose(.01,float(baseline),z,act,speed,float(ks[0]),gain);cb,rb=b.choose(.01,float(baseline),z,act,speed,float(ks[0]),gain)
        if abs(ca-cb)>1e-8:
            alias=dict(shared_policy_observation=x.tolist(),initial_filters=[-.06,.06],commands=[ca,cb],reasons=[ra,rb],
                interpretation='Distinct valid internal filter states alias under20-channel observation and can yield different transitions. Reachability of this exact pair is not proved; this diagnoses lack of a guaranteed Markov state, not the measured cause of the performance gap.')
            break
    result['filter_state_alias']=alias
    assert alias is not None,'No alias found; do not claim it was demonstrated'
    result['conclusions']=[
        'A10ms poll age is not10ms actor inference: inference, queue/service, delivery age and monitor deadline are separate.',
        'Steep old age gain suppresses otherwise-valid commands; removing it is a new evaluated control variant, not retroactive repair of old results.',
        'Same-tick zero-service simulation overstates freshness relative to periodic asynchronous delivery; new cases require >=1control tick.',
        'Some misses include >10ms control work and some are already late on release; elapsed/threadCPU proxies do not establish an OS-only cause.',
        'Two hidden filter states can share all policy features; a causal filter-history input would require a new versioned model/normalizer and matched training, never filling old oracle channels silently.',
        'A1% relative improvement over the student remains a frozen selection rule, not a software defect that can be fixed by lowering the threshold.'
    ]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(cases=cases,state_alias_demonstrated=alias is not None),indent=2))


if __name__=='__main__':main()
