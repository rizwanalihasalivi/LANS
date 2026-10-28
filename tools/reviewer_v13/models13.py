"""Recover all paired historical actors, with a lossless causal-history bridge."""
import boot13
import numpy as np
import torch
from stable_baselines3 import PPO
from causal_student import load_causal

VALUES = np.array([-.08, -.04, 0., .04, .08])


def original(pair, source):
    if source == 'student':
        return load_causal(boot13.ROOT/f'docs/research/causal-interface-2026-10-26/models/{(701,802,903)[pair]}')
    with (boot13.ROOT/f'docs/research/reviewer-causal-v1/training/finetune-{(2701,2802,2903)[pair]}/policy.zip').open('rb') as file:
        return PPO.load(file, device='cpu')


def export(model, student=False, bridge=True):
    if student:
        features = model
        layers = (model.net[0], model.net[2], model.net[4])
    else:
        features = model.policy.features_extractor
        layers = (model.policy.mlp_extractor.policy_net[0], model.policy.mlp_extractor.policy_net[2], model.policy.action_net)
    data = dict(mean=features.mean.numpy().copy(), std=features.std.numpy().copy())
    for i, layer in enumerate(layers):
        data[f'w{i}'] = layer.weight.detach().numpy().T.copy()
        data[f'b{i}'] = layer.bias.detach().numpy().copy()
    if bridge:
        # Original ABI mandates x14==0. Changing this unused channel therefore
        # preserves every original logit, including a possible nonzero mean.
        data['b0'] -= data['mean'][14]/data['std'][14]*data['w0'][14]
        data['mean'][14] = 0.; data['std'][14] = 1.; data['w0'][14] = 0.
    return data


def logits(model, x):
    x = np.asarray(x, np.float32)
    return np.tanh(np.tanh((x-model['mean'])/model['std']@model['w0']+model['b0'])@model['w1']+model['b1'])@model['w2']+model['b2']


def residual(model, obs):
    return float(VALUES[int(logits(model, obs[None, :]).argmax(1)[0])])

