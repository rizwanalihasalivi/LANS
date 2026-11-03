"""Enable the actual optimized deterministic branch and test fresh development cells.

The v2 outcomes remain unchanged. All numeric promotion criteria remain unchanged.
This module configures the existing frozen campaign library in its own process;
it neither edits nor patches the v2 source files on disk.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import numpy as np
from tools.unified_campaign import campaign as base
from tools.unified_campaign.study import make_case as original_case,run_episode as original_episode
from integrations.unified_lans.inference import sha,load_policy
from integrations.unified_lans.physics import Command


def configure(training_root):
    training_root=Path(training_root).resolve()
    protocol=copy.deepcopy(base.PROTOCOL)
    protocol.update(version=3,new_training_steps=0,
        change='hybrid includes the same optimized deterministic candidate grid as the strong comparator',
        rationale='v2 longer merge trials exposed failures in the simple-residual branch while optimized search survived',
        unchanged='same learned weights, actuator limits, freshness, cost, nominal/plant parameters and numerical gate thresholds',
        v2_training_protocol_sha256=sha(training_root/'protocol.json'),
        policy_hashes={str(s):sha(training_root/f'policies/seed-{s}/policy.zip') for s in protocol['seeds']},
        development_namespace=1410000,reserved_namespace=1910000,
        development_phase=6.,development_amplitude=1.1,reserved_phase=17.,reserved_amplitude=1.2,
        interpretation='finite fresh development repair; extra deterministic search is not a PPO learning gain')
    old_files=base.source_files
    base.source_files=lambda:sorted([*old_files(),*Path(__file__).parent.glob('*.py')])
    base.PROTOCOL=protocol
    # Verification-only repair: the frozen v2 auditor omitted this import.
    # Model, controller, raw records, tolerances and gate thresholds are unchanged.
    base.Command=Command

    def cases(stage,index):
        case=original_case(stage,index)
        rng=np.random.default_rng((1410000 if stage=='development' else 1910000)+index)
        case.update(lateral=float(rng.uniform(.15,.45))*case['mirror'],heading=float(rng.uniform(-.015,.015)),
            phase=6. if stage=='development' else 17.,amplitude=1.1 if stage=='development' else 1.2,
            network_seed=(1510000 if stage=='development' else 2010000)+index)
        return case

    def episode(case,mode,model=None,grid=False,seconds=6.):
        result,rows=original_episode(case,mode,model,grid=grid or mode=='hybrid',seconds=seconds)
        if mode=='hybrid':result['mode']='hybrid'
        return result,rows

    def frozen_endpoints(root):
        root=base.check(root)
        for seed in protocol['seeds']:
            source=training_root/f'policies/seed-{seed}';target=root/f'policies/seed-{seed}'
            assert sha(source/'policy.zip')==protocol['policy_hashes'][str(seed)]
            if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source,target)
            model=load_policy(target);assert model.num_timesteps==protocol['steps_per_seed']
            assert sha(target/'policy.zip')==protocol['policy_hashes'][str(seed)]
        print('Frozen three v2 endpoints reused; zero additional training steps.',flush=True)

    base.make_case=cases;base.run_episode=episode;base.train=frozen_endpoints


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--training',default='results/python-campaign-v2')
    parser.add_argument('--output',default='results/python-improvement-v3')
    args=parser.parse_args();configure(args.training);root=Path(args.output)
    if not root.exists():base.prepare(root)
    base.train(root);base.evaluate(root,'development');gate=base.report(root,'development')
    stress_pass=base.robustness(root)
    if gate['passed'] and stress_pass:
        base.evaluate(root,'reserved');reserved=base.report(root,'reserved')
        base.write(root/'PYTHON_PERFORMANCE_GATE.json',dict(passed=reserved['passed'],development=gate,
            robustness=True,reserved=reserved,wall_worker_required=True,webots='NOT_RUN'))
    else:
        base.write(root/'PYTHON_PERFORMANCE_GATE.json',dict(passed=False,development=gate,
            robustness=stress_pass,reserved='NOT_RUN',wall_worker='NOT_RUN',webots='NOT_RUN'))
        print('STOP: unchanged Python gate failed; reserved and Webots remain unopened.',flush=True)


if __name__=='__main__':main()
