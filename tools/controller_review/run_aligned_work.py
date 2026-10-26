"""One-command finite v3 study, exact portable export and full-controller smoke."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--smoke-python',default=sys.executable);args=p.parse_args()
    out=ROOT/'docs/research/reviewer-aligned-v3';env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
        NUMBA_CACHE_DIR='/tmp/lans-aligned-kit-cache',MPLCONFIGDIR='/tmp/lans-aligned-kit-mpl')
    def run(cmd,log,cwd=ROOT):
        with log.open('w') as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    def publish(label):
        if not args.publish:return
        subprocess.run(['git','add','-f',str(out.relative_to(ROOT))],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:subprocess.run(['git','commit','-m',label],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        subprocess.run(['git','-c','credential.helper=!gh auth git-credential','push','origin',branch],cwd=ROOT,check=True)
    out.mkdir(parents=True,exist_ok=True)
    if not (out/'completion-status.json').exists():
        run([sys.executable,ROOT/'tools/reviewer_v3/run3.py']+(['--publish'] if args.publish else []),out/'resume-all.log')
    export=out/'export'
    if not export.exists():run([sys.executable,HERE/'export_aligned_actors.py','--run',out,'--output',export],out/'actor-export.log')
    for seed in (701,802,903):assert (export/str(seed)/'parity.json').exists(),'Partial export preserved; inspect before retry'
    run([sys.executable,HERE/'verify_aligned_training.py','--run',out],out/'training-verification.log')
    portable=out/'portable-actor'
    if not portable.exists():run([sys.executable,ROOT/'tools/laptop/export_bundle.py','--model-root',export,'--output',portable],out/'portable-export.log')
    assert (portable/'manifest.json').exists(),'Partial portable export preserved; inspect before retry'
    kit=out/'LANS_Aligned_Python310_Kit'
    if not kit.exists():run([sys.executable,HERE/'export_full_laptop.py','--actor-dir',portable,'--profile','aligned','--output',kit],out/'full-kit-export.log')
    manifest=json.loads((kit/'bundle-manifest.json').read_text())
    for n,h in manifest['sha256'].items():assert hashlib.sha256((kit/n).read_bytes()).hexdigest()==h
    smoke=out/'kit-smoke'
    if not (smoke/'summary.json').exists():
        if smoke.exists():raise RuntimeError('Partial smoke preserved; inspect before retry')
        run([args.smoke_python,kit/'tools/controller_review/laptop_full_controller.py','--profile','aligned','--models',kit/'actor',
            '--seconds','3','--output',smoke],out/'kit-smoke.log',cwd=kit)
    run([args.smoke_python,kit/'tools/controller_review/verify_full_laptop.py','--run',smoke,'--models',kit/'actor'],out/'kit-verification.log',cwd=kit)
    publish('tools: verify exact aligned PPO export and portable full-controller kit')
    final=out/'final-update.md';text=final.read_text()
    marker='## Portable aligned-controller package and verified references'
    if marker not in text:
        text+='\n'+marker+'\n\nThe new Python3.10 kit now includes the actual v3 endpoint actors and the same aligned supervisor, not the old25k diagnostic. Torch-to-NumPy class parity is checked on all24,300 archived DEV observations per actor; this is export parity, not a new performance evaluation. It is a research diagnostic irrespective of selection outcome.\n\nClean Linux smoke uses five3-second cases with seed701; all three actors undergo export/golden checks. See kit-smoke/verification.json. Smoke functionality does not certify strict timing or target Windows/macOS behaviour. Actual target laptop measurements remain pending. Request/response identity and original timestamps are checked at receipt.\n\nRun the extracted kit using RUN_WINDOWS.cmd or `bash RUN_MAC.command`; return laptop-results/Results.zip. No physical readiness is claimed.\n\n### Simulation-to-worker timing boundary\n\nOffline zero-service simulation can deliver a proposal in the same control tick. A separate worker polled once per10ms loop normally delivers on a later tick. The retained original age-gain is steep: the0.25 cap becomes about0.00458 at10ms observation age, even for fast inference. Identical supervisor code therefore does not establish identical effective authority under different delivery timing. Packet age, inference duration, post-inference service delay and loop release lateness must remain separate. This new study does not establish that the residual tracking gains transfer to a real asynchronous deployment. The kit records actual timestamps/authority for this boundary; neither packet freshness nor functional fallback is proof of physical timing safety.\n\n'+(out/'verified-references.md').read_text()+'\n'
    text=text.replace('reviewer-followup-v2/sleep','v2 sleep').replace('reviewer-followup-v2/absolute','v2 absolute')
    text=text.replace('reviewer-aligned-v3/absolute_100us','v3 sleep + spin').replace('reviewer-aligned-v3/dedicated_spin','v3 full spin')
    text=text.replace('| absolute_100us |','| Sleep + 100µs spin |').replace('| dedicated_spin |','| Full spin |')
    text=text.replace('| oldppo |','| Old PPO |').replace('| ppo |','| New PPO |').replace('| lqr |','| LQR |')
    pieces=re.split(r'(`[^`]*`)',text)
    for i,part in enumerate(pieces):
        if part.startswith('`'):continue
        part=re.sub(r'(?<=[A-UW-Za-uw-z])(?=\d)',' ',part)
        part=re.sub(r'(?<=\d)(?=[A-UW-Za-uw-zµ])',' ',part)
        part=re.sub(r',(?=\S)',', ',part)
        pieces[i]=part.replace('100 k','100,000').replace('25 k','25,000')
    text=''.join(pieces);final.write_text(text)
    for suffix in ('docx','pdf'):
        cmd=['pandoc',final,'-o',out/f'final-update.{suffix}']
        if suffix=='pdf':cmd+=['--pdf-engine=xelatex','-V','mainfont=DejaVu Serif','-V','geometry:margin=22mm','-V','fontsize=10pt','-V','papersize=a4']
        subprocess.run(list(map(str,cmd)),check=True)
    with zipfile.ZipFile(out/'LANS_Aligned_Reports.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n in ('final-update.md','final-update.docx','final-update.pdf','verified-references.md','completion-status.json','summary.json','decision.json','timing-diagnosis.json','episodes.csv'):
            z.write(out/n,n)
    qa={}
    for n in ('LANS_Aligned_Reports.zip','LANS_Aligned_Python310_Kit.zip','final-update.docx'):
        with zipfile.ZipFile(out/n) as z:assert z.testzip() is None
        qa[n]=hashlib.sha256((out/n).read_bytes()).hexdigest()
    (out/'artifact-quality.json').write_text(json.dumps(dict(archive_crc_pass=True,sha256=qa,actual_windows_macos_run=False),indent=2)+'\n')
    publish('docs: publish aligned experiment evidence and version-verified primary references')
    print((out/'completion-status.json').read_text())


if __name__=='__main__':main()
