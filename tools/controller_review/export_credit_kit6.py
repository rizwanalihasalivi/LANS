"""Package three-seed target rerun; do not label a diagnostic as a winner."""
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
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run.resolve();decision=json.loads((out/'decision.json').read_text())
    models=out/'selected-portable-actor' if decision['selected'] is not None else ROOT/'docs/research/reviewer-history-v5/portable-actor'
    kit=out/'LANS_Current_Python310_Kit'
    subprocess.run([sys.executable,str(ROOT/'tools/controller_review/export_full_laptop.py'),'--profile','fresh_history','--actor-dir',str(models),'--output',str(kit)],check=True)
    shutil.copy2(ROOT/'tools/controller_review/laptop_campaign6.py',kit/'tools/controller_review/laptop_campaign6.py')
    for name in ('RUN_WINDOWS.cmd','RUN_MAC.command','README.md'):
        f=kit/name;f.write_text(f.read_text().replace('laptop_full_controller.py','laptop_campaign6.py').replace('--run laptop-results --models actor','--run laptop-results/seed-701 --models actor'))
    (kit/'RUN_WINDOWS.cmd').write_text('''@echo off
setlocal
cd /d "%~dp0"
py -3.10 -c "import sys; assert sys.version_info[:2]==(3,10)" >nul 2>nul
if errorlevel 1 goto use_python
py -3.10 -m venv .venv
goto install
:use_python
python -c "import sys; assert sys.version_info[:2]==(3,10)" >nul 2>nul
if errorlevel 1 goto python_missing
python -m venv .venv
:install
if errorlevel 1 goto failed
.venv\\Scripts\\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\\Scripts\\python.exe tools\\controller_review\\laptop_campaign6.py --profile fresh_history --output laptop-results
if errorlevel 1 goto failed
echo Completed. Send laptop-results\\Results.zip for review.
pause
exit /b 0
:python_missing
echo Python 3.10 was not found. Install Python 3.10 and enable its PATH or py launcher.
:failed
echo Benchmark did not complete. Keep the error above and any partial results; do not overwrite them.
pause
exit /b 1
''')
    readme=kit/'README.md';readme.write_text('''# Three-actor LANS target-laptop rerun

Extract the entire ZIP first. Windows: double-click RUN_WINDOWS.cmd (Python3.10). macOS: run `bash RUN_MAC.command` with Python3.10 installed. First installation requires internet. No Torch, GPU or Webots is needed.

The command runs all three frozen actors, each with nominal,20ms service wait,1000ms service wait,CPU stress and worker-crash cases. Each case lasts13seconds after warmup:195seconds total measured windows, plus startup and independent replay. It does not retry failed timing cases. Keep the laptop plugged in and close unrelated applications. Results remain in a new laptop-results folder; send laptop-results/Results.zip, which includes all raw CSVs and independent replay checks. No device identifiers are collected.

Any original10ms deadline miss fails observed strict timing. Functional fallback, actual nominal learned assistance and timing are reported separately. The software plant pauses during host stalls. This does not validate physical sensors, communications, actuators or continuous-time vehicle safety.

RESEARCH_STATUS.json identifies whether these are a newly development-selected model or the unchanged v5 diagnostic because no new model qualified. Neither status is vehicle deployment approval or a completed confirmation study.

'''+readme.read_text())
    status=dict(development_selected=decision['selected'],research_diagnostic_only=True,
        packaged_models='selected-portable-actor' if decision['selected'] is not None else 'unchanged v5 nohistory portable actor',
        actual_user_laptop_execution_pending=True,full_promotion=False)
    (kit/'RESEARCH_STATUS.json').write_text(json.dumps(status,indent=2)+'\n')
    hashes={str(f.relative_to(kit)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in kit.rglob('*') if f.is_file() and f.name!='bundle-manifest.json'}
    (kit/'bundle-manifest.json').write_text(json.dumps(dict(sha256=hashes,scope='three-seed software diagnostic; actual target execution pending'),indent=2)+'\n')
    archive=kit.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in kit.rglob('*'):
            if f.is_file():z.write(f,str(Path(kit.name)/f.relative_to(kit)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(archive,archive.stat().st_size)

if __name__=='__main__':main()
