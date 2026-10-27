import boot12
import json
import shutil
import numpy as np
import torch
from stable_baselines3 import PPO
from study11 import logits
from checkpoint12 import atomic_json, digest


def main(run):
    out = run/'actors'; out.mkdir(exist_ok=True)
    checks = []
    rng = np.random.default_rng(12032)
    x = rng.normal(0, .2, (2000, 20)).astype(np.float32)
    x[:, [16, 17]] = 0.; x[:, [15, 19]] = rng.uniform(0, 1, (len(x), 2))
    for pair, seed in enumerate((701, 802, 903)):
        for name, old in (('student', 'student_rk'), ('oldppo', 'oldppo_rk'), ('prior', 'newppo_rk')):
            shutil.copy2(boot12.ROOT/f'docs/research/reviewer-training-v11/actors/{old}-{seed}.npz', out/f'{name}-{pair}.npz')
        for arm in ('continued', 'explore'):
            folder = run/f'{arm}-{pair}'
            endpoint = json.loads((folder/'complete.json').read_text())['checkpoint']
            with (folder/'checkpoints'/endpoint['folder']/'model.zip').open('rb') as f:
                model = PPO.load(f, device='cpu')
            features = model.policy.features_extractor
            data = dict(mean=features.mean.numpy().copy(), std=features.std.numpy().copy())
            for i, layer in enumerate((model.policy.mlp_extractor.policy_net[0], model.policy.mlp_extractor.policy_net[2], model.policy.action_net)):
                data[f'w{i}'] = layer.weight.detach().numpy().T.copy()
                data[f'b{i}'] = layer.bias.detach().numpy().copy()
            with torch.no_grad():
                expected = np.concatenate([model.policy.action_net(model.policy.mlp_extractor.forward_actor(
                    model.policy.extract_features(torch.from_numpy(xx[None, :])))).numpy() for xx in x])
            actual = np.concatenate([logits(data, xx[None, :]) for xx in x])
            mismatch = int(np.count_nonzero(expected.argmax(1) != actual.argmax(1)))
            error = float(np.max(np.abs(expected-actual)))
            assert mismatch == 0 and error < 1e-4, (arm, pair, mismatch, error)
            np.savez_compressed(out/f'{arm}-{pair}.npz', **data)
            checks.append(dict(arm=arm, pair=pair, rows=len(x), class_disagreements=mismatch, max_abs_error=error))
    atomic_json(out/'manifest.json', dict(checks=checks, feature_schema='causal_recovery_history_v9',
        controller='forecast_rk_v12', diagnostic_only=True,
        sha256={f.name: digest(f) for f in out.glob('*.npz')}))

