"""Persisted version of the bounded provenance check executed during completion."""
from pathlib import Path
import json,zipfile,hashlib
R=Path('/workspace/LANS');W=R/'integrations/webots';O=Path('/workspace/lans-aris-audit')
d=json.loads((O/'completion-check-results.json').read_text());checks=[];different=[]
for e in d['training_metadata']:
 p=R/e['path'];m=json.loads(p.read_text());q=p.with_name('policy.zip')
 with zipfile.ZipFile(q) as z:data=json.loads(z.read('data'))
 assert data['num_timesteps']==m['steps'] and data['seed']==m['seed'],str(p)
 assert hashlib.sha256(q.read_bytes()).hexdigest()==m['policy_sha256'],str(q)
 for n,h in m['source_sha256'].items():
  arc=p.parent/'source'/n
  assert arc.exists() and hashlib.sha256(arc.read_bytes()).hexdigest()==h,(str(p),n)
  cur=W/'research'/n
  if not cur.exists() or cur.read_bytes()!=arc.read_bytes():different.append({'checkpoint':str(p.relative_to(R)),'source':n})
 checks.append({'checkpoint':str(p.relative_to(R)),'steps':data['num_timesteps'],'seed':data['seed'],'policy_matches_existing_digest':True,'archived_sources_match_existing_digests':True})
d['checkpoint_zip_metadata_checks']=checks;d['historical_sources_different_from_current']=different
missing_names=['REFERENCE_AUDIT.csv','REFERENCE_AUDIT.md','REVIEWER_EVIDENCE_STATUS.csv','REVISION_STATUS.md','references.json','revision_analysis_source.py','rewrite_complete.py','verify_equations.py']
with zipfile.ZipFile(R/'research-inputs/LANS_JSA_Supplementary_Package (2)(4).zip') as z:
 d['supplement_zip_members']=len(z.namelist())
 d['supplement_missing_named_members']=[m for m in missing_names if not any(n.endswith('/'+m) for n in z.namelist())]
(O/'completion-check-results.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps({'checkpoint_metadata_checks':len(checks),'source_differences':different,'supplement_missing':d['supplement_missing_named_members']},indent=2))
