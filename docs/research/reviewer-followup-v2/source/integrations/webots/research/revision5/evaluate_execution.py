"""Development evaluation through the exact execution-aware training environment.

Known random-sine training distribution; not reserved/native/generalization data.
Every candidate uses the same physics, observations, gate and reward path.
"""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from execution_env import ExecutionEnv


def predict(policy, observation):
    if np.asarray(observation).shape != (20,):
        raise ValueError('execution-v5 requires 20 observation components')
    if policy is None:
        return np.array([0.], dtype=np.float32)
    if tuple(policy.observation_space.shape) != (20,) or tuple(policy.action_space.shape) != (1,):
        raise ValueError('incompatible policy: require execution-v5 20-component observation and scalar action')
    action, _ = policy.predict(observation, deterministic=True)
    action = np.asarray(action).reshape(-1)
    if action.shape != (1,) or not np.isfinite(action).all():
        raise ValueError('one finite normalized action required')
    return np.clip(action, -1., 1.)


def episode(policy, seed, service_ticks, randomize=False, trace=False):
    env = ExecutionEnv(seed=seed, randomize=randomize, service_ticks=service_ticks)
    observation, _ = env.reset(seed=seed)
    errors, records = [], []
    try:
        while True:
            action = predict(policy, observation)
            observation, reward, failed, truncated, info = env.step(action)
            errors.append(info['error'])
            if trace:
                records.append(dict(step=len(errors)-1, normalized_action=float(action[0]), reward=reward, **info))
            if failed or truncated:
                break
        total = 800
        return dict(seed=seed, service_ticks=service_ticks, randomize=randomize, speed=env.speed,
                    path=str(env.path), survived=not failed, steps=len(errors), scheduled_steps=total,
                    rmse=float(np.sqrt(np.mean(np.square(errors)))),
                    penalized_rmse=float(np.sqrt((sum(e*e for e in errors)+(total-len(errors))*6.25)/total))), records
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, help='20-feature execution-aware model, never legacy 9-feature weights')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seeds', type=int, nargs='+', default=[101, 202])
    parser.add_argument('--service-ticks', type=int, nargs='+', choices=[0,1,2,10], default=[0,1,2,10])
    parser.add_argument('--randomize', action='store_true')
    args = parser.parse_args()
    import torch
    from stable_baselines3 import PPO
    torch.set_num_threads(1)
    policy = PPO.load(args.policy, device='cpu') if args.policy else None
    if policy is not None:
        metadata = json.loads((args.policy.parent/'complete.json').read_text())
        if (metadata.get('observation_dimensions') != 20 or metadata.get('residual_scale_rad') != .08
                or metadata.get('steps') != policy.num_timesteps):
            raise ValueError('execution-policy metadata does not match the 20-feature/.08-rad checkpoint')
        predict(policy, np.zeros(20, dtype=np.float32))
    args.output.mkdir(parents=True, exist_ok=False)
    summary = []
    for seed in args.seeds:
        for ticks in args.service_ticks:
            for name, selected in [('lqr',None), *([('execution_policy',policy)] if policy is not None else [])]:
                row, records = episode(selected, seed, ticks, args.randomize, trace=True)
                row['method'] = name; summary.append(row)
                with (args.output/f'{name}-{seed}-{ticks}.csv').open('w',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=records[0],lineterminator='\n');writer.writeheader();writer.writerows(records)
    with (args.output/'episodes.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=summary[0],lineterminator='\n');writer.writeheader();writer.writerows(summary)
    (args.output/'scope.json').write_text(json.dumps(dict(scope='development training-distribution execution check only',
        policy=str(args.policy) if args.policy else None, interface='execution-v5', observation_components=20,
        reward_normalization='training rewards only; deterministic inference uses raw fixed-scaled observations',
        final_reserved=False, native=False),indent=2)+'\n')
    print(args.output/'episodes.csv')


if __name__ == '__main__':
    main()
