"""One sequential, resumable post-learning V13 verification pipeline.

Completed measured missions are consumed with their failures intact; this
command never deletes a result or reruns a timing mission for a better sample.
The teacher/training budget remains the separately frozen training protocol.
"""
from pathlib import Path
import argparse,json,subprocess,sys,time
from .learning import ROOT,DATA
from .runtime import sha

STAGES=('continued','validation','final','runtime','native','qualify','audit','package')
COMMANDS={
    'continued':('train','continued'),
    'validation':('evaluate','validation'),
    'final':('evaluate','final'),
    'runtime':('complete','runtime'),
    'native':('complete','native'),
    'qualify':('complete','assess'),
    'audit':('verify','--reuse'),
    'package':('package',),
}


def read(path):return json.loads(Path(path).read_text())


def completed(stage):
    """Only a complete frozen artifact can skip execution, never a partial log."""
    from . import evaluate,complete
    if stage=='continued':
        path=DATA/'continued-bc/summary.json'
        if not path.exists():return False
        evaluate.frozen_policies();return True
    if stage in ('validation','final'):
        out=DATA/stage
        if not (out/'summary.json').exists():return False
        protocol=evaluate.verify_protocol(out);rows=read(out/'summary.json')
        assert len(rows)==protocol['episodes']
        assert read(out/'assessment.json')==evaluate.assess(rows,protocol['bootstrap_seed'])
        return True
    if stage in ('runtime','native'):
        out=DATA/'completion'/stage
        if not (out/'summary.json').exists():return False
        p=read(out/'protocol.json');s=read(out/'summary.json');complete.check_freeze(p,out)
        assert not s['execution_errors'], 'An incomplete measured campaign cannot be silently retried'
        assert s['assessment']==read(out/'assessment.json')==complete.assess_stage(s['records'],p)
        assert s['assessment']['complete']
        return True
    if stage=='qualify':
        path=DATA/'completion/qualification.json'
        if not path.exists():return False
        p=read(path)
        for name,digest in p['input_hashes'].items():assert sha(ROOT/name)==digest
        for name,digest in p['campaign_hashes'].items():assert sha(DATA/'completion'/name)==digest
        return True
    if stage=='audit':
        path=DATA/'verification.json'
        if not path.exists():return False
        p=read(path)
        if not p['all_requested_stages_verified']:return False
        for name,digest in p['input_hashes'].items():assert sha(ROOT/name)==digest
        return True
    if stage=='package':
        from .package import OUT
        if not (OUT/'SEAL.json').exists():return False
        from tools.unified_control_v9.package import verify
        verify(OUT);return True
    raise ValueError(stage)


def run(start='continued',resume=False):
    assert start in STAGES
    # Keep live packaging output outside the tree being sealed. The packager
    # copies completed experiment logs and excludes its own changing output.
    folder=ROOT.parent/'cloud-setup';folder.mkdir(parents=True,exist_ok=True)
    events=folder/'ppo-complete-v13-pipeline-journal.jsonl'
    for stage in STAGES[STAGES.index(start):]:
        if completed(stage):
            if not resume:raise RuntimeError(f'{stage} already complete; use --resume to consume existing evidence')
            print('V13 PIPELINE',stage,'existing complete frozen evidence retained',flush=True)
            continue
        log=folder/('ppo-complete-v13-pipeline-'+stage+'.log')
        if log.exists():raise RuntimeError(f'Prior {stage} attempt retained at {log}; inspect its error before any new experiment')
        module,*arguments=COMMANDS[stage]
        command=[sys.executable,'-u','-m','tools.ppo_complete_v13.'+module,*arguments]
        started=time.time()
        print('V13 PIPELINE START',stage,str(log),flush=True)
        with log.open('x') as stream:
            result=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        event=dict(stage=stage,returncode=result.returncode,started_unix=started,ended_unix=time.time(),
            log=str(log),log_sha256=sha(log),orchestrator_sha256=sha(__file__))
        with events.open('a') as stream:stream.write(json.dumps(event,allow_nan=False)+'\n');stream.flush()
        if result.returncode:raise subprocess.CalledProcessError(result.returncode,command)
        assert completed(stage),('CLI ended without complete evidence',stage)
        print('V13 PIPELINE COMPLETE',stage,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-stage',choices=STAGES,default='continued')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();run(args.from_stage,args.resume)


if __name__=='__main__':main()
