import importlib.util,json
from pathlib import Path
root=Path('/workspace/LANS-webots/integrations/webots')
spec=importlib.util.spec_from_file_location('native_run',root/'research/revision2/native/run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
output=Path('/tmp/lans-native-audit-smoke');output.mkdir(exist_ok=False)
sources={name:m.sha(root/name) for name in m.SOURCES}
results={}
for mode in ['lqr','gated_residual']:
    case=dict(mu=.9,contact_scale=1.,noise=1,sensor_delay_steps=0,delay_ms=0,mode=mode,speed=20,path='dlc220',seed=880501,policy_seed=0,scenario='nominal',duration=3.,gate_config={'horizon_steps':20,'relative_margin':.01})
    if mode!='lqr':case['policy']=str(root/'results/research-training/residual-0/policy.zip');case['policy_sha256']=m.sha(Path(case['policy']))
    _,results[mode]=m.run(case,mode,output,sources)
(output/'summary.json').write_text(json.dumps(dict(purpose='current-code native interface smoke only, no performance inference',results=results),indent=2)+'\n')
assert all(value['survived'] and value['steps']==300 for value in results.values())
print('2/2 native smoke cases completed; no performance selection')
