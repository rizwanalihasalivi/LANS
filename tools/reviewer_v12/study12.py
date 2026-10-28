"""Episode-level resume and typed raw evidence on a predeclared fresh matrix."""
import boot12
import argparse
import csv
import itertools
import json
import math
import os
import uuid
import numpy as np
from env12 import Env
from env11 import Env as LegacyEnv
from study11 import FIELDS, logits
from planner12 import propose
from checkpoint12 import atomic_json, digest

P = json.loads((boot12.HERE/'protocol.json').read_text())


def make_env(case, source, scenario):
    return (LegacyEnv if source == 'legacy_prior' else Env)(case=case, source=source, scenario=scenario)


def residual_for(env, source, model):
    if env.ctrl.pending is not None: return 0.
    if source == 'negative': return -.04
    if source == 'positive': return .04
    if source == 'planner':
        return propose(env.ctrl, env.estimate, env.state[5], env.measured_speed,
                       env.ctrl.previews, env.gain, env.gains, env.tick*.01)
    if model is not None:
        return [-.08, -.04, 0., .04, .08][int(logits(model, env.obs[None, :]).argmax(1)[0])]
    return 0.


def episode(case, source, scenario, model, path):
    env = make_env(case, source, scenario); env.reset()
    rows, raw, queries, histories = [], [], [], []
    while True:
        active = env.ctrl.pending is None
        raw.append(env.raw.copy())
        queries.append(env.obs.copy() if active else np.full(20, np.nan, np.float32))
        meta = env.query_meta
        histories.append([meta[k] for k in ('estimated_delay_s', 'used_horizon_s', 'completed_history_samples', 'last_completed_sequence')] if active else [0., 0., 0., -1.])
        residual = residual_for(env, source, model)
        _, _, failed, done, row = env.step_residual(residual)
        rows.append(row)
        if failed or done: break
    data = {k: np.array([math.nan if r[k] is None else r[k] for r in rows]) for k in FIELDS}
    data.update(raw=np.array(raw), query=np.array(queries), forecast_history=np.array(histories),
                reason=np.array([r['reason'] for r in rows]))
    temp = path.with_name(path.name+'.partial-'+uuid.uuid4().hex)
    with temp.open('wb') as f:
        np.savez_compressed(f, **data); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
    n, h = len(rows), env.horizon
    return dict(steps=n, scheduled=h, survived=not failed,
        rmse_m=math.sqrt((sum(r['lateral_error']**2 for r in rows)+(h-n)*6.25)/h),
        heading_rmse_rad=math.sqrt(sum(r['heading_error']**2 for r in rows)/n),
        rate_rms_rad_s=math.sqrt(sum(r['steering_rate']**2 for r in rows)/n),
        active_ticks=sum(r['weight'] > 0 for r in rows),
        movement_rad=sum(abs(r['steering_rate'])*.01 for r in rows), trace_sha256=digest(path))


def models_for(run, pair):
    models = {}
    for source in ('student', 'oldppo', 'prior', 'continued', 'explore'):
        with np.load(run/f'actors/{source}-{pair}.npz', allow_pickle=False) as f:
            models[source] = {k: f[k].copy() for k in f.files}
    models['legacy_prior'] = models['prior']
    return models


def main(run, pair):
    out = run/f'pair-{pair}'; (out/'traces').mkdir(parents=True, exist_ok=True)
    models = models_for(run, pair); rows = []; cfg = P['development']
    for speed, path, sign, scenario in itertools.product(cfg['speeds'], cfg['paths'], cfg['mirrors'], cfg['scenarios']):
        noise = cfg['noise_base']+pair*100000+speed*1000+cfg['paths'].index(path)*100+cfg['scenarios'].index(scenario)*10
        case = (speed, path, sign, 'tire' if scenario == 'tire' else 'nominal', noise)
        for source in cfg['sources']:
            name = f'{speed}-{path}-{sign}-{scenario}-{source}'
            trace = out/'traces'/(name+'.npz'); record = out/'traces'/(name+'.json')
            if record.exists():
                row = json.loads(record.read_text())
                if digest(trace) != row['trace_sha256']: raise ValueError('Changed completed trace: '+name)
            else:
                metrics = episode(case, source, scenario, models.get(source), trace)
                row = dict(pair=pair, speed=speed, path=path, mirror=sign, scenario=scenario,
                           source=source, noise_id=noise, trace=trace.name, **metrics)
                atomic_json(record, row)
            rows.append(row)
        print(pair, speed, path, sign, scenario, len(rows), flush=True)
    with (out/'episodes.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0], lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    atomic_json(out/'complete.json', dict(episodes=len(rows), episodes_sha256=digest(out/'episodes.csv')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--run', type=boot12.Path, required=True)
    parser.add_argument('--pair', type=int, choices=range(3), required=True)
    a = parser.parse_args(); main(a.run, a.pair)
