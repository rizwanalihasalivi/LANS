"""Posthoc matched branch audit on v11 states; never a deployable oracle.

Twelve preselected states per nominal/tire, speed/path cell (six accepted and
six cost-rejected where available). One packet's planned assistance until its
original expiry, then feedback LQR. No future neural outputs are assumed.
Hidden plant parameters and recorded future noise belong ONLY to this offline
diagnostic, and are never exposed to the controller or training inputs.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/reviewer_v12'))
import boot12
import copy
import itertools
import json
import math
import numpy as np
from env11 import Env
from checkpoint12 import atomic_json, digest


def branch(original, filtered, residual, weight, assisted):
    env = copy.deepcopy(original)
    counter = 0
    def command(t, baseline, *unused):
        nonlocal counter, filtered
        if counter and counter < assisted: filtered += (1-math.exp(-.01/.3))*(residual-filtered)
        w = weight if counter < assisted else 0.
        value = float(np.clip(baseline+w*filtered, -.5, .5))
        env.ctrl.weight = w; env.ctrl.filtered = filtered
        env.ctrl.last_command = value
        counter += 1
        return value, 'offline_counterfactual'
    env.ctrl.choose = command
    cost = lateral = 0.
    for i in range(100):
        _, reward, failed, done, row = env.step_residual(0.)
        cost += .01*(-reward)
        lateral += .01*row['lateral_error']**2
        if failed or done:
            cost += (99-i)*.1
            return cost, lateral, False
    return cost, lateral, True


def main():
    prior = ROOT/'docs/research/reviewer-training-v11'
    seal = json.loads((prior/'evidence-hashes.json').read_text())['sha256']
    rng = np.random.default_rng(12034); rows = []
    for speed, path, scenario in itertools.product((15, 25), ('sine120', 'dlc220'), ('nominal', 'tire')):
        name = f'pair-0/traces/{speed}-{path}-1-{scenario}-newppo_rk.npz'
        assert digest(prior/name) == seal[name]
        with np.load(prior/name, allow_pickle=False) as f: data = {k: f[k].copy() for k in f.files}
        n = len(data['command']); selected = set()
        for reason in ('accepted', 'cost'):
            eligible = np.flatnonzero((data['reason'] == reason) & (np.arange(n) < n-101))
            selected.update(rng.choice(eligible, min(6, len(eligible)), replace=False).tolist())
        noise = 1726000000+speed*1000+('sine120', 'dlc220').index(path)*100+('nominal', 'tire').index(scenario)*10
        env = Env(case=(speed, path, 1, scenario, noise), source='newppo_rk', scenario=scenario); env.reset()
        for tick in range(n):
            if tick in selected:
                c = copy.copy(env.ctrl)
                c.choose(tick*.01, env.baseline, env.estimate, env.state[5], env.measured_speed, env.curvature, env.gain)
                predicted_base, predicted_candidate = c.last_costs
                weight = min(.25, env.ctrl.weight+.05)
                seq, observed, residual = env.ctrl.packet
                assisted = max(0, math.ceil((.05-(tick*.01-observed)-1e-12)/.01))
                assert np.isfinite([predicted_base, predicted_candidate]).all()
                physical_base, lateral_base, alive0 = branch(env, c.filtered, residual, 0., 0)
                physical_candidate, lateral_candidate, alive1 = branch(env, c.filtered, residual, weight, assisted)
                rows.append(dict(speed=speed, path=path, scenario=scenario, tick=tick,
                    logged_reason=str(data['reason'][tick]), weight=weight, assisted_steps=assisted,
                    predicted_benefit=predicted_base-predicted_candidate,
                    physical_cost_benefit=physical_base-physical_candidate,
                    physical_relative_benefit=(physical_base-physical_candidate)/max(physical_base, 1e-12),
                    physical_lateral_energy_benefit=lateral_base-lateral_candidate,
                    both_branches_survived=alive0 and alive1))
            _, _, _, _, actual = env.step_residual(float(data['proposed_residual'][tick]))
            assert abs(actual['command']-data['command'][tick]) < 1e-12
    groups = {}
    for scenario, reason in itertools.product(('nominal', 'tire'), ('accepted', 'cost')):
        group = [r for r in rows if r['scenario'] == scenario and r['logged_reason'] == reason]
        groups[scenario+'/'+reason] = dict(samples=len(group),
            physical_benefit_above_01pct=sum(r['physical_relative_benefit'] > .001 for r in group),
            physical_harm_above_01pct=sum(r['physical_relative_benefit'] < -.001 for r in group),
            predicted_actual_sign_disagreements=sum((r['predicted_benefit'] > 0) != (r['physical_cost_benefit'] > 0) for r in group))
    result = dict(source_sha256=digest(Path(__file__)), prior_seal_sha256=digest(prior/'evidence-hashes.json'),
        rows=rows, groups=groups, samples=len(rows),
        limitations='Finite posthoc conditional sample on one v11 actor/noise group, right-mirror only. Current estimate versus nonlinear plant/observer/reference/noise discrepancies are jointly included. Future noise/true parameters are used only in offline branches. No robust safety proof, unbiased population error rate, optimality ceiling, training targets or deployable oracle claim.')
    atomic_json(ROOT/'docs/research/ppo-audit-v12/prediction-branches.json', result)
    print(json.dumps(groups, indent=2))


if __name__ == '__main__': main()
