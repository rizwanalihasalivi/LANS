"""Technical attribution index, generated only after complete raw verification."""
from pathlib import Path
import json,re
import numpy as np
from integrations.unified_lans.inference import sha
from .core import DATA,dump
from .anchor_evaluate import paired


def main():
    load=lambda p:json.loads(p.read_text())
    audit=load(DATA/'verification.json')
    assert audit['all_requested_checks_passed'] and audit['anchored_evaluation']['episodes']==216 and audit['continued_bc_evaluation']['episodes']==216
    variants={name:load(DATA/f'{directory}/assessment.json') for name,directory in
        [('unregularized_ppo','evaluation'),('anchored_ppo','anchor-evaluation'),('continued_bc','continued-bc-evaluation')]}
    anchored=load(DATA/'anchor-evaluation/summary.json');control=load(DATA/'continued-bc-evaluation/summary.json')
    incremental=paired(control,anchored)
    base=load(DATA/'evaluation/summary.json');by_delay={}
    for delay in (0.,.05,.1):
        reference=[r for r in base if r['mode']=='adaptive' and r['case']['delay']==delay]
        denominator=np.mean([r['rmse_m'] for r in reference]);group={}
        for name,rr in [('old',[r for r in base if r['mode']=='old']),('bc',[r for r in base if r['mode']=='bc']),
            ('unregularized',[r for r in base if r['mode']=='ppo']),('anchored',anchored),('continued_bc',control)]:
            selected=[r for r in rr if r['case']['delay']==delay]
            group[name]=dict(mean_rmse_m=float(np.mean([r['rmse_m'] for r in selected])),
                gain_vs_adaptive_percent=float(100*(1-np.mean([r['rmse_m'] for r in selected])/denominator)),
                failures=sum(r['failed'] for r in selected),ppo_ticks=sum(r['ppo_ticks'] for r in selected))
        by_delay[str(delay)]=group
    tests=Path('/workspace/cloud-setup/ppo-benefit-v10-full-tests.log');match=re.search(r'(\d+) passed',tests.read_text());assert match
    result=dict(source_sha256=sha(__file__),audit_sha256=sha(DATA/'verification.json'),
        successful_new_ppo_steps=98304,initial_teacher_transitions=7611,interrupted_transitions=3072,
        initial_bc_epochs_per_seed=32,continued_bc_updates_per_seed=1280,
        evaluation_episodes=1296,unique_tests=int(match.group(1)),variants=variants,
        anchored_vs_continued_bc=incremental,
        descriptive_by_delay=by_delay,
        strong_ppo_contribution_established=variants['anchored_ppo']['primary_success'] and incremental['ci95_percent'][0]>0,
        requested_30_achieved=variants['anchored_ppo']['requested_30'] and incremental['gain_percent']>=30,
        interpretation='Report absolute incremental gains on this same grid; BC-only gains cannot be attributed solely to PPO. No actual-runtime, Webots, hardware or general novelty claim.')
    dump(DATA/'ATTRIBUTION.json',result);print('Technical attribution JSON saved.')


if __name__=='__main__':main()
