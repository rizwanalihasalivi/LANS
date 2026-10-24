"""Independent checkpoint/optimizer/normalization and complete-grid audit."""
import csv,hashlib,itertools,json,math,pickle,sys
from statistics import mean
from pathlib import Path
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv,VecNormalize
HERE=Path(__file__).resolve().parent;RESEARCH=HERE.parent;ROOT=RESEARCH.parent
sys.path[:0]=[str(HERE),str(RESEARCH)]
from pilot_env import PilotEnv
from comparison import configure_lqr
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    torch.set_num_threads(1);configure_lqr()
    out=ROOT/'results/revision3-extended';initial=ROOT/'results/revision3-pilots'
    protocol=json.loads((HERE/'extension.json').read_text());proof=[]
    for candidate in protocol['top_two']:
        for seed in protocol['training_seeds']:
            name=f'{candidate}-{seed}';a=initial/name;b=out/name;m=json.loads((b/'complete.json').read_text())
            assert m['steps']==300000 and m['additional_steps']==200000 and m['initial_policy_sha256']==sha(a/'policy.zip') and m['initial_normalization_sha256']==sha(a/'normalization.pkl')
            assert m['policy_sha256']==sha(b/'policy.zip')
            for n,d in m['source_sha256'].items():assert sha(b/'source'/n)==d and sha(RESEARCH/n)==d
            constructor_seeds=[1000000+seed*100+i for i in range(8)]
            env=DummyVecEnv([lambda i=i:PilotEnv(constructor_seeds[i],m['candidate_config']) for i in range(8)])
            env=VecNormalize.load(a/'normalization.pkl',env)
            before=PPO.load(a/'policy.zip',env=env,device='cpu');after=PPO.load(b/'policy.zip',device='cpu')
            assert before.num_timesteps==100000 and after.num_timesteps==300000
            optimizer_steps=lambda model:sorted({int(v['step'].item()) for v in model.policy.optimizer.state_dict()['state'].values()})
            original_steps=optimizer_steps(before);extended_steps=optimizer_steps(after)
            assert min(original_steps)>0 and min(extended_steps)>max(original_steps)
            # SB3 load seeds the VecEnv from model.seed, overriding constructor defaults.
            effective_reset_seeds=list(env.venv._seeds)
            assert effective_reset_seeds==[seed+i for i in range(8)]
            with (a/'normalization.pkl').open('rb') as f:old_norm=pickle.load(f)
            with (b/'normalization.pkl').open('rb') as f:new_norm=pickle.load(f)
            assert abs((new_norm.ret_rms.count-old_norm.ret_rms.count)-200000)<1e-6
            completed=0
            for p in b.glob('*.monitor.csv'):
                with p.open() as f:
                    next(f)
                    completed+=sum(int(row['l']) for row in csv.DictReader(f))
            assert 0<=200000-completed<6400
            proof.append(dict(candidate=candidate,seed=seed,initial_steps=before.num_timesteps,total_steps=after.num_timesteps,additional_completed_episode_steps=completed,initial_optimizer_step_counters=original_steps,final_optimizer_step_counters=extended_steps,normalization_count_before=float(old_norm.ret_rms.count),normalization_count_after=float(new_norm.ret_rms.count),effective_initial_reset_seeds=effective_reset_seeds,initial_policy_sha256=m['initial_policy_sha256'],policy_sha256=m['policy_sha256']))
            env.close()
    result=dict(verified=True,runs=proof,continuation_note='PPO weights, Adam state and reward-normalization statistics continue from100k. Environments restart; SB3 load overrides the planned constructor seed offset with model.seed+i. Thus the planned fresh offset is NOT effective. Both candidates get identical seed treatment. This is not uninterrupted300k training, and repeated initial environment streams are a limitation; no weights or gate were retuned in response.',full_training_started=False,user_decision_required=True)
    decision=json.loads((out/'decision.json').read_text())
    assert sha(out/'development.csv')==decision['development_csv_sha256']
    for n,d in decision['source_sha256'].items():assert sha(RESEARCH/n)==d and sha(out/'source'/n)==d
    with (out/'development.csv').open() as f:rows=list(csv.DictReader(f))
    base=json.loads((HERE/'protocol.json').read_text())
    keys=[(int(r['seed']),int(r['speed']),r['path'],r['scenario'],r['method']) for r in rows]
    expected=set(itertools.product(protocol['training_seeds'],base['speeds'],base['paths'],base['scenarios'],protocol['methods']))
    assert len(keys)==len(set(keys))==len(expected)==360 and set(keys)==expected
    lookup=dict(zip(keys,rows))
    for key,r in lookup.items():
        assert float(r['max_rate'])<=.3500001 and math.isfinite(float(r['penalized_rmse']))
        if r['survived']=='True':assert r['steps']==r['scheduled_steps']
        if r['scenario']=='latency100':
            baseline=lookup[key[:4]+('lqr',)]
            assert r['penalized_rmse']==baseline['penalized_rmse'] and float(r['active_fraction'])==0
    for a in decision['assessments']:
        chosen=[r for r in rows if r['method']==a['candidate']]
        assert math.isclose(mean(float(r['penalized_rmse']) for r in chosen),a['mean_penalized_rmse'],abs_tol=1e-12)
        assert sum(r['survived']=='True' for r in chosen)==a['survived']
    result['development_episodes']=360
    result['development_survived']=sum(r['survived']=='True' for r in rows)
    report=out/'report.md'
    text=report.read_text().replace('restarts environments on a common fresh seed offset','restarts environments at SB3 model.seed+i (the constructor offset was overridden; see continuation-audit.json)')
    report.write_text(text)
    (out/'continuation-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified all four checkpoint/optimizer/normalization continuations to300k; SB3 reset-seed caveat recorded.')
if __name__=='__main__':main()
