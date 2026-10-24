"""Fail if the requested budgets, seed/scenario grid or checkpoint provenance are incomplete."""
import csv,hashlib,json,math
from pathlib import Path
import torch
from stable_baselines3 import PPO

ROOT=Path(__file__).resolve().parents[1]
torch.set_num_threads(1)
verified=[]
for role in ('full','residual'):
    for seed in range(5):
        folder=ROOT/f'results/research-training/{role}-{seed}'
        metadata=json.loads((folder/'complete.json').read_text())
        assert metadata['steps']==1000000 and metadata['seed']==seed and metadata['role']==role
        assert metadata['policy_sha256']==hashlib.sha256((folder/'policy.zip').read_bytes()).hexdigest()
        for filename,digest in metadata['source_sha256'].items():
            assert hashlib.sha256((folder/'source'/filename).read_bytes()).hexdigest()==digest,(folder,filename)
        if role=='residual':
            assert metadata['tracking_protocol_sha256']==hashlib.sha256((ROOT/'research/tracking-protocol.json').read_bytes()).hexdigest()
        model=PPO.load(folder/'policy.zip',device='cpu')
        assert model.num_timesteps==1000000 and model.seed==seed
        completed_steps=0;episodes=0
        for logfile in folder.glob('episodes-*.csv.monitor.csv'):
            with logfile.open() as stream:
                next(stream)
                for row in csv.DictReader(stream):completed_steps+=int(row['l']);episodes+=1
        assert 0<=1000000-completed_steps<6400
        verified.append({'role':role,'seed':seed,'steps':model.num_timesteps,'completed_episode_steps':completed_steps,'episodes':episodes,'policy_sha256':metadata['policy_sha256']})
        del model
folder=ROOT/'results/research-evaluation'
with (folder/'episodes.csv').open() as stream:rows=list(csv.DictReader(stream))
assert len(rows)==810
keys={(int(r['seed']),r['method'],int(r['speed_m_s']),r['path'],int(r['delay_ms'])) for r in rows}
expected={(s,m,v,p,d) for s in range(5) for m in ['lqr','ppo','residual','fusion','no_supervisor','fixed_weight'] for v in (15,20,25) for p in ['dlc220','sine120','sine160'] for d in (0,20,100)}
assert keys==expected
for row in rows:
    assert 0<int(row['steps'])<=int(row['scheduled_steps'])
    if row['survived']=='True':assert row['steps']==row['scheduled_steps']
    assert float(row['max_actuator_rate_rad_s'])<=.3500001
    assert math.isfinite(float(row['failure_penalized_rmse_m']))
for name,digest in json.loads((folder/'source-hashes.json').read_text()).items():
    assert hashlib.sha256((folder/'source'/name).read_bytes()).hexdigest()==digest
physical=json.loads((ROOT/'results/research-core/physical-audit.json').read_text())
assert len(physical['transfer'])==45 and len(physical['tracking'])==9
report={'verified':True,'final_training_steps':sum(x['steps'] for x in verified),'trained_policies':verified,
        'surrogate_evaluation_episodes':len(rows),'webots_transfer_runs':45,'corrected_webots_lqr_runs':9,
        'note':'Budget and data integrity verification; not a guarantee of convergence, safety or superiority.'}
(ROOT/'results/research-core/campaign-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('Verified 10 policies / 10,000,000 final training steps / 810 evaluation episodes / 45 Webots transfer runs')
