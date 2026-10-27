"""Recover metadata only after a verified completed model save; never train or alter weights."""
import argparse,hashlib,json
from pathlib import Path
import torch
from stable_baselines3 import PPO

p=argparse.ArgumentParser();p.add_argument('folder',type=Path);args=p.parse_args()
folder=args.folder
if (folder/'complete.json').exists():raise FileExistsError('already finalized')
torch.set_num_threads(1)
model=PPO.load(folder/'policy.zip',device='cpu')
assert model.num_timesteps==1000000
assert (folder/'normalization.pkl').exists()
progress=json.loads((folder/'progress.json').read_text());assert progress['steps']==1000000
source=folder/'source';hashes={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in source.iterdir() if x.is_file()}
profile=json.loads((source/'final-training-protocol.json').read_text());assert profile['steps_per_seed_per_role']==1000000
role,seed=folder.name.rsplit('-',1)
assert int(seed)==model.seed
metadata={'seed':int(seed),'role':role,'steps':model.num_timesteps,'wall_s':progress['wall_s'],
          'wall_time_scope':'through final rollout only; recovered after metadata-writer KeyError, after policy and normalization had been saved',
          'training_profile':'positive_survival_v2','final_training_protocol_sha256':hashes['final-training-protocol.json'],
          'protocol_sha256':hashes['protocol.json'],'comparison_protocol_sha256':hashes['comparison-protocol.json'],
          'source_sha256':hashes,'policy_sha256':hashlib.sha256((folder/'policy.zip').read_bytes()).hexdigest(),
          'metadata_recovery':'verified saved PPO.num_timesteps == 1000000, seed, final progress, source snapshots and normalization presence; weights unchanged',
          'recovery_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(folder/'complete.json').write_text(json.dumps(metadata,indent=2)+'\n');print(folder.name,'verified and finalized')
