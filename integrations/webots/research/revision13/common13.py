"""Frozen revision13 grid, identities and small provenance helpers."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = HERE.parents[3]
P = json.loads((HERE / 'protocol.json').read_text())
G = json.loads((RESEARCH / 'revision6/protocol.json').read_text())
RESULTS = RESEARCH.parent / 'results'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def geometries(phase):
    return P['reserved_geometries'] if phase == 'reserved' else P['development_geometries']


def roads(phase):
    return [name + ('_left' if sign == 1 else '_right')
            for name in geometries(phase) for sign in P['signs']]


def road_spec(name):
    base, direction = name.rsplit('_', 1)
    if direction not in ('left', 'right'):
        raise ValueError('unknown road orientation')
    value = P['geometry'][base]
    sign = 1 if direction == 'left' else -1
    return tuple(float(x) for x in value['parameters'] + [sign]), value['length_m'], base, sign


def noise_id(phase, repetition, speed, road, region):
    _, _, base, _ = road_spec(road)
    return (P['phases'][phase]['noise_base'] + repetition * 100000 + speed * 1000
            + list(P['geometry']).index(base) * 100 + P['scenarios'].index(region))


def method_spec(method):
    if method == 'lqr':
        return 'legacy', 0, 'lqr'
    for variant, code in P['variants'].items():
        prefix = variant + '_'
        if method.startswith(prefix) and method[len(prefix):] in P['proposers']:
            return variant, code, method[len(prefix):]
    raise ValueError('unknown controller method: ' + method)


def methods(phase, selection=None):
    if phase != 'reserved':
        return P['phases'][phase]['methods']
    if not selection or selection.get('selected_candidate') not in P['selection_candidates']:
        raise ValueError('reserved stage requires selected development candidate')
    gate, _, _ = method_spec(selection['selected_candidate'])
    return ['lqr', 'legacy_student', 'lateral_fixed_m004', 'lateral_fixed_p004',
            gate + '_fixed_m004', gate + '_fixed_p004', gate + '_student']


def student_hashes():
    return {str(seed): {name: sha(RESULTS / f'revision8-student/students/{seed}' / name)
                       for name in ('student.pt', 'normalization.npz', 'complete.json')}
            for seed in P['student_seeds']}


def sources():
    # Native code has its own freeze; this snapshot covers the surrogate driver.
    local = ['protocol.json', 'common13.py', 'dynamics13.py', 'gate13.py',
             'run13.py', 'report13.py', 'test_contracts13.py', 'test_report13.py', 'test_run13.py']
    shared = ['revision12/gate12.py', 'revision8/bootstrap.py', 'revision8/student.py',
              'revision8/protocol.json', 'revision7/kernels.py', 'revision7/bootstrap.py',
              'revision5/bootstrap.py', 'revision2/gating.py', 'revision2/plant.py',
              'revision6/protocol.json', 'core.py', 'protocol.json', 'comparison.py',
              'comparison-protocol.json']
    return ['revision13/' + name for name in local] + shared
