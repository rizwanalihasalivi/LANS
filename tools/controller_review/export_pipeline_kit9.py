"""Build the frozen causal-history controller's Torch-free target bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from export_full_laptop import FILES
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run.resolve();decision=json.loads((out/'decision.json').read_text());arm=decision['selected'] or 'legacy_history'
    kit=out/'LANS_Causal_Python310_Kit';kit.mkdir(exist_ok=False)
    files=FILES.copy()
    files+=[f'tools/reviewer_v{v}/{n}' for v,nn in ((3,['boot3.py','aligned.py','protocol.json']),(4,['boot4.py','interface4.py','scalar_cost.py','protocol.json']),(7,['boot7.py','compensation.py','protocol.json']),(8,['boot8.py','recovery8.py','expiry_cost8.py','protocol.json']),(9,['boot9.py','features9.py','runtime9.py','verify_laptop9.py','protocol.json'])) for n in nn]
    files+=['tools/controller_review/verify_timing9.py','tools/controller_review/laptop_campaign9.py']
    for name in files:
        target=kit/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    shutil.copytree(out/'runtime-actors'/arm,kit/'actor')
    (kit/'requirements.txt').write_text('numpy==1.23.5\nscipy==1.10.1\nnumba==0.57.1\ngymnasium==0.28.1\n')
    template=(ROOT/'docs/research/reviewer-credit-v6/LANS_Current_Python310_Kit/RUN_WINDOWS.cmd').read_text()
    template=template.replace('laptop_campaign6.py','laptop_campaign9.py').replace('--profile fresh_history','--profile history_comp --budget-guard')
    (kit/'RUN_WINDOWS.cmd').write_text(template)
    (kit/'RUN_MAC.command').write_text('''#!/bin/bash
set -e
cd "$(dirname "$0")"
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/controller_review/laptop_campaign9.py --profile history_comp --budget-guard --output laptop-results
''')
    (kit/'RESEARCH_STATUS.json').write_text(json.dumps(dict(arm=arm,selected=decision['selected'],diagnostic_only=decision['selected'] is None,hardware_validation_pending=True,vehicle_ready=False),indent=2)+'\n')
    (kit/'README.md').write_text('''# LANS causal-history laptop kit — Python 3.10

Extract the ZIP first. Windows: double-click RUN_WINDOWS.cmd. macOS: run `bash RUN_MAC.command` with Python 3.10 installed. First dependency installation needs internet. No Torch, GPU or Webots is required. Use mains power and close unrelated programs. Do not run simultaneous benchmarks.

The command runs three frozen actors, each on five 13-second software-plant cases (195 measured seconds plus warmup/replay): nominal, 20ms and 1000ms post-inference worker waits, CPU contention and crash. Computation, IPC, service wait and proposal age are separately recorded. The unmodified original 10ms target remains the deadline; the 1ms guard skips optional work, never shifts the target. Misses are failures even when fallback works. Output must be a NEW folder; failed/partial data are retained.

Before execution every bundled source/model file is checked against bundle-manifest.json. Every original target, returned actor output, all issued input vectors, past-only timing history, recovery/expiry decision and software-plant transition are independently replayed. Return laptop-results/Results.zip, including failures. Source hashes provide reproducibility, not attestation of physical hardware.

The separately versioned 20-channel causal_recovery_history_v9 profile includes filtered residual, past completed-response EWMA and age of the previous qualifying proposal. It never includes the current request's future completion time. This profile must not be substituted into old model manifests. LQR continues using current estimated state. Learned authority expires at 50ms regardless of a favorable prediction. The compensation forecast is capped at 40ms; this does not compensate for arbitrary LQR feedback or physical sensor delay.

RESEARCH_STATUS.json distinguishes a selected controller from a diagnostic actor. A cloud smoke test cannot substitute for your laptop result. Software-plant survival does not establish continuous-time stability, physical sensing/communication/actuator performance or real-vehicle readiness. Strict observed timing and nominal learned assistance are separate results; no hard real-time guarantee is claimed.
''')
    hashes={str(f.relative_to(kit)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in kit.rglob('*') if f.is_file()}
    (kit/'bundle-manifest.json').write_text(json.dumps(dict(sha256=hashes,scope='Frozen causal-history software-plant target campaign'),indent=2)+'\n')
    archive=kit.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in kit.rglob('*'):
            if f.is_file():z.write(f,str(Path(kit.name)/f.relative_to(kit)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(archive)

if __name__=='__main__':main()
