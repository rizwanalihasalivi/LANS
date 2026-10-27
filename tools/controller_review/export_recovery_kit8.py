import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run.resolve();decision=json.loads((out/'decision.json').read_text());raw=decision['selected']=='ppo_raw'
    profile='recovery_raw' if raw else 'recovery_compensated'
    models=ROOT/('docs/research/reviewer-history-v5/portable-actor' if raw else 'docs/research/reviewer-delay-compensation-v7/actor')
    kit=out/'LANS_Recovery_Python310_Kit'
    subprocess.run([sys.executable,str(ROOT/'tools/controller_review/export_full_laptop.py'),'--profile',profile,'--actor-dir',str(models),'--output',str(kit)],check=True)
    shutil.copy2(ROOT/'tools/controller_review/laptop_campaign6.py',kit/'tools/controller_review/laptop_campaign6.py')
    template=ROOT/'docs/research/reviewer-credit-v6/LANS_Current_Python310_Kit/RUN_WINDOWS.cmd'
    (kit/'RUN_WINDOWS.cmd').write_text(template.read_text().replace('--profile fresh_history',f'--profile {profile} --budget-guard'))
    mac=kit/'RUN_MAC.command';mac.write_text(mac.read_text().replace('laptop_full_controller.py','laptop_campaign6.py').replace('--profile '+profile,'--profile '+profile+' --budget-guard'))
    (kit/'README.md').write_text('''# Experimental LANS recovery and expiry-aware controller

Extract the ZIP first. Windows: RUN_WINDOWS.cmd; macOS: `bash RUN_MAC.command` with Python3.10 installed. Internet is needed for first dependency installation; no Torch/GPU/Webots is required. The Windows script also accepts an available Python3.10 `python` when the `py` launcher is absent and keeps error messages visible.

Three frozen actors each run five13second cases after warmup: nominal,20ms and1000ms post-inference worker waits, CPU contention and worker crash. Total measured windows195seconds, plus startup and independent raw replay. Use power supply and close unrelated apps. Send laptop-results/Results.zip. Output must be new; failed/partial runs are preserved rather than overwritten or retried away.

This version requires three distinct qualifying proposals, retains recovery/filter memory only within a50ms liveness window, and sets authority zero on every stale tick. Prediction uses only the current proposal lifetime, followed by LQR continuation. The launcher enables an optional1ms reserve to skip optional work near the original10ms deadline. This reserve is not WCET certification; any original deadline miss still fails strict observed timing. Future input prediction uses only completed-response history and remains capped40ms.

RESEARCH_STATUS.json records that no new controller is promoted if the development criteria fail. Frozen actors were not retrained for the revised gate. Functional fallback, nominal learned assistance and strict timing are separate fields. Fixed-step plant survival does not validate physical sensor/communication/actuator delays, continuous-time safety or real-vehicle readiness. Actual laptop execution is pending until YOU run this kit.
''')
    (kit/'RESEARCH_STATUS.json').write_text(json.dumps(dict(profile=profile,development_selected=decision['selected'],diagnostic_only=decision['selected'] is None,vehicle_ready=False,actual_laptop_run_pending=True),indent=2)+'\n')
    hashes={str(f.relative_to(kit)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in kit.rglob('*') if f.is_file() and f.name!='bundle-manifest.json'}
    (kit/'bundle-manifest.json').write_text(json.dumps(dict(sha256=hashes,scope='Three-seed software-plant target diagnostic'),indent=2)+'\n')
    archive=kit.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in kit.rglob('*'):
            if f.is_file():z.write(f,str(Path(kit.name)/f.relative_to(kit)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(archive,archive.stat().st_size)

if __name__=='__main__':main()
