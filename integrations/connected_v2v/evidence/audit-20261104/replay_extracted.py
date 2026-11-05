import json
import os
from pathlib import Path
import sys

root=Path('/workspace/lans-setup/v2v-audit-20261104-extracted/results/v2v-audit-20261104-v1')
source=(root/'source').resolve();sys.path.insert(0,str(source));os.environ['LANS_V2V_REPO']=str(source)
mode=sys.argv[1]
if mode=='python':
    from integrations.connected_v2v.settling.study import replay
    path=root/'python-validation/combined-16-21001'
    result=replay(path)
else:
    from integrations.connected_v2v.settling.native import verify
    path=root/'native-validation/combined-12-22003'
    result=verify(path)
assert result['passed']
modules={}
for name,module in list(sys.modules.items()):
    if name.split('.')[0] in ('integrations','controllers','models') and getattr(module,'__file__',None):
        p=Path(module.__file__).resolve();assert p.is_relative_to(source),(name,str(p))
        modules[name]=str(p.relative_to(source))
print(json.dumps(dict(passed=True,case=path.name,project_modules=modules,
    scope='extracted frozen-source controller replay; native physics was not rerun'),indent=2))
