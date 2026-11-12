"""Isolated native Webots launchers; readiness is separate from final transfer."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,time
from .runtime import sha

ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent


def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def copy_protos(project):
    hashes={};manifest=ROOT/'integrations/webots/runtime-sha256.txt'
    roots=[ROOT/'integrations/webots/.runtime',Path('/workspace/LANS/integrations/webots/.runtime')]
    for line in manifest.read_text().splitlines():
        digest,name=line.split()
        if not name.startswith('protos/'):continue
        source=next((root/name for root in roots if (root/name).is_file()),None)
        if source is None:raise FileNotFoundError('Restore the pinned Webots PROTO cache: '+name)
        assert sha(source)==digest,('Native PROTO source changed',name)
        target=project/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        hashes[name]=digest
    assert len(hashes)==5
    return hashes


def run_process(command,env,log,timeout):
    import signal
    process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:code=process.wait(timeout=timeout)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5.)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait()
        raise
    if code:raise subprocess.CalledProcessError(code,command)


def readiness(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    project=output/'project';(project/'worlds').mkdir(parents=True)
    protos=copy_protos(project)
    controller=project/'controllers/v13_readiness';controller.mkdir(parents=True)
    source=HERE/'native_assets/readiness.py';target=controller/'v13_readiness.py';shutil.copyfile(source,target)
    worldsource=ROOT/'integrations/webots/worlds/publication_v9.wbt'
    world=worldsource.read_text().replace('../.runtime/protos','../protos').replace('controller "publication_v9"','controller "v13_readiness"')
    worldpath=project/'worlds/readiness.wbt';worldpath.write_text(world)
    protocol=dict(role='environment_readiness_only',webots='R2025a',duration_s=2.,physics_step_s=.001,
        policy_tested=False,final_controller_tested=False,native_ego_physics=True,protos=protos,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),source,worldsource,ROOT/'tools/cloud/run-webots.sh')},
        generated_world_sha256=sha(worldpath),limitation='Single physical vehicle; no tracking, traffic, learned-policy or final safety claim.')
    dump(output/'protocol.json',protocol);env=os.environ.copy();env['LANS_NATIVE_OUTPUT']=str(output)
    start=time.monotonic()
    with (output/'console.log').open('w') as log:
        run_process(['bash',str(ROOT/'tools/cloud/run-webots.sh'),'--stdout','--stderr','--batch','--mode=fast','--no-rendering',str(worldpath)],env,log,120.)
    result=json.loads((output/'summary.json').read_text());assert result['passed'] and result['ticks']==2000
    assert not result['policy_tested'] and not result['final_controller_tested']
    dump(output/'provenance.json',dict(protocol_sha256=sha(output/'protocol.json'),raw_sha256=sha(output/'ticks.jsonl'),
        world_sha256=sha(worldpath),elapsed_wall_s=time.monotonic()-start,summary_sha256=sha(output/'summary.json')))
    print(json.dumps(result),flush=True);return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--readiness',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.readiness:parser.error('Final native transfer requires a frozen Python gateway and is not environment readiness')
    readiness(args.output)


if __name__=='__main__':main()
