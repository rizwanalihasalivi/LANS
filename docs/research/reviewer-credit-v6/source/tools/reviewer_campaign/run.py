"""One-command, resumable reviewer campaign; publish completed verified milestones."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'docs/research/reviewer-causal-v1')
    p.add_argument('--publish',action='store_true')
    p.add_argument('--smoke-only',action='store_true')
    args=p.parse_args()
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
               MPLCONFIGDIR='/tmp/lans-campaign-mpl',NUMBA_CACHE_DIR='/tmp/lans-campaign-numba')
    protocol=json.loads((HERE/'protocol.json').read_text())
    manifest_path=args.output/'manifest.json'
    sources=list(HERE.glob('*.py'))+[HERE/'protocol.json']
    sources += [ROOT/'tools/controller_review/causal_student.py']
    sources += [ROOT/'integrations/webots/controllers/reviewer_validation/reviewer_validation.py']
    sources += [ROOT/'tools/controller_review'/name for name in (
        'realtime_optimized.py','realtime_kernels.py','realtime_causal.py','realtime_student.py',
        'verify_realtime_optimized.py','verify_native_causal.py','native_causal.py')]
    sources += list((ROOT/'integrations/webots/research').glob('*.py'))
    for revision in ('revision2','revision4','revision5','revision7','revision8','revision9'):
        sources += list((ROOT/'integrations/webots/research'/revision).glob('*.py'))
        file=ROOT/'integrations/webots/research'/revision/'protocol.json'
        if file.exists():sources.append(file)
    for seed in protocol['student_seeds']:
        sources += list((ROOT/f'docs/research/causal-interface-2026-10-26/models/{seed}').glob('*'))
    hashes={str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sources if file.is_file()}
    manifest=dict(protocol=protocol,hashes=hashes,
        start_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    if manifest_path.exists():
        old=json.loads(manifest_path.read_text())
        if old['protocol'] != protocol or old['hashes'] != hashes:
            raise ValueError('Frozen source/model/protocol changed: use a new campaign directory; never overwrite evidence')
    else:
        for relative in hashes:
            target=args.output/'source'/relative
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    status_file=args.output/'status.json'
    status=json.loads(status_file.read_text()) if status_file.exists() else dict(
        stages={},external=dict(physical_vehicle='unavailable: fresh physical measurements required',
        laptop_rerun='pending user target-machine results',
        formal_safety='not established; limited assumptions only',
        primary_reference_verification='uploaded five PDFs read; publication metadata / broader search incomplete',
        published_algorithm_reproduction='not implemented; no superiority claim',
        native_ppo='pending gated transfer and timing assessment',
        hard_realtime='not established; prior10ms deadline tests failed'))
    def save():status_file.write_text(json.dumps(status,indent=2)+'\n')
    def command(cmd,log):
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('w') as handle:
            subprocess.run(cmd,cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,check=True)
    def publish(label):
        if not args.publish:return
        relative=args.output.relative_to(ROOT)
        subprocess.run(['git','add','-f',str(relative)],cwd=ROOT,check=True)
        subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
        if subprocess.run(['git','diff','--cached','--quiet'],cwd=ROOT).returncode:
            subprocess.run(['git','commit','-m',f'research: {label}'],cwd=ROOT,check=True)
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()
        if not branch:raise ValueError('named branch required for publication')
        subprocess.run(['git','-c',"credential.helper=!gh auth git-credential",'push','origin',branch],cwd=ROOT,check=True)
    def stage(name,work):
        if status['stages'].get(name,{}).get('state')=='complete':
            print(f'RESUME {name}',flush=True);return
        status['stages'][name]=dict(state='running');save()
        print(f'START {name}',flush=True)
        try:
            work()
        except Exception as error:
            status['stages'][name]=dict(state='failed',error=str(error));save()
            raise
        status['stages'][name]=dict(state='complete');save()
        publish(name)
        print(f'COMPLETE {name}',flush=True)
    stage('protocol-frozen',lambda:None)
    stage('causal-contract-tests',lambda:command([sys.executable,str(HERE/'test_contract.py'),'-v'],args.output/'contract-tests.log'))
    training=args.output/'training'
    training.mkdir(exist_ok=True)
    def train_job(item):
        pair,arm=item
        folder=training/f'{arm}-{protocol["seeds"][pair]}'
        if (folder/'complete.json').exists():return
        if folder.exists():raise ValueError(f'incomplete training folder retained: {folder}; investigate, do not silently retry')
        command([sys.executable,str(HERE/'train.py'),'--pair',str(pair),'--arm',arm,'--output',str(folder)],
                training/f'{folder.name}.log')
    def train_all():
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(train_job,[(pair,arm) for pair in range(3) for arm in protocol['arms']]))
        metas=[json.loads(p.read_text()) for p in training.glob('*/complete.json')]
        assert len(metas)==6 and sum(m['steps'] for m in metas)==150000
    stage('bounded-causal-training',train_all)
    stage('ppo-worker-export',lambda:command([sys.executable,str(HERE/'export.py'),
        '--training',str(training),'--output',str(args.output/'export')],args.output/'export.log'))
    grid='smoke' if args.smoke_only else 'development'
    def evaluate_all(name):
        folder=args.output/name;folder.mkdir(exist_ok=True)
        def job(pair):
            shard=folder/f'pair-{pair}'
            if (shard/'complete.json').exists():return
            if shard.exists():raise ValueError(f'incomplete evaluation retained: {shard}')
            command([sys.executable,str(HERE/'evaluate.py'),'--training',str(training),
                     '--output',str(shard),'--pair',str(pair),'--grid',name],folder/f'pair-{pair}.log')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(job,range(3)))
        command([sys.executable,str(HERE/'report.py'),'--run',str(args.output),'--grid',name],folder/'verification.log')
    stage(f'{grid}-verified',lambda:evaluate_all(grid))
    decision=json.loads((args.output/grid/'decision.json').read_text())
    if grid=='development' and decision['eligible']:
        confirmation_manifest=args.output/'confirmation-manifest.json'
        if not confirmation_manifest.exists():
            confirmation_manifest.write_text(json.dumps(dict(protocol=protocol,
                frozen_checkpoint_steps=25000,development_decision=decision),indent=2)+'\n')
            publish('freeze conditional confirmation before opening')
        stage('confirmation-verified',lambda:evaluate_all('confirmation'))
    else:
        status['confirmation']=dict(state='unopened',reason=decision['reasons']);save()
    def real_worker():
        cfg=protocol['real_worker']
        command([sys.executable,str(HERE/'realtime.py'),'--output',str(args.output/'real-worker'),
            '--model-root',str(args.output/'export'),'--seconds',str(cfg['seconds_each']),
            '--noise-base',str(cfg['noise_base']),'--cases',*cfg['cases']],args.output/'real-worker.log')
        command([sys.executable,str(ROOT/'tools/controller_review/verify_realtime_optimized.py'),
            '--run',str(args.output/'real-worker'),'--model-root',str(args.output/'export')],
            args.output/'real-worker-verification.log')
        evidence=json.loads((args.output/'real-worker/summary.json').read_text())
        status['external']['hard_realtime']=('Observed timing passed finite cloud test, not guaranteed WCET'
            if evidence['timing_pass'] else 'FAIL: observed10ms deadline misses; no100Hz guarantee')
        save()
    stage('actual-worker-verified',real_worker)
    def native():
        command([sys.executable,str(HERE/'native.py'),'--output',str(args.output/'native'),
                 '--models',str(args.output/'export')],args.output/'native.log')
        command([sys.executable,str(ROOT/'tools/controller_review/verify_native_causal.py'),
                 '--run',str(args.output/'native'),'--models',str(args.output/'export')],
                 args.output/'native-verification.log')
        evidence=json.loads((args.output/'native/verification.json').read_text())
        status['external']['native_ppo']=dict(interface_pass=evidence['native_interface_verification_pass'],
            observed_wall_timing_pass=evidence['strict_native_wall_timing_pass'],
            scope='PPO-export/shared supervisor native interface; no generalization or vehicle claim')
        save()
    stage('native-interface-verified',native)
    stage('reviewer-response-report',lambda:command([sys.executable,str(HERE/'write_response.py'),
         '--run',str(args.output),'--grid',grid],args.output/'write-response.log'))
    print(json.dumps(status,indent=2),flush=True)


if __name__=='__main__':main()
