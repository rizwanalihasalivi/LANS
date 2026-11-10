"""Small reproducibility record for observed cloud/native timing."""
from pathlib import Path
from importlib.metadata import version
import argparse,hashlib,json,os,platform,time


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[2];binary=root/'integrations/webots/.runtime/webots/bin/webots-bin'
    def value(path):
        try:return Path(path).read_text().strip()
        except OSError:return None
    cpu=value('/proc/cpuinfo') or '';model=next((line.split(':',1)[1].strip() for line in cpu.splitlines() if line.startswith('model name')),None)
    r=dict(recorded_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),python=platform.python_version(),platform=platform.platform(),
        cpu_model=model,cpu_quota=value('/sys/fs/cgroup/cpu.max'),cpu_pressure=value('/proc/pressure/cpu'),
        parent_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
        native_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),native_binary_bytes=binary.stat().st_size,
        numba_cache_dir=os.environ.get('NUMBA_CACHE_DIR'),
        versions={n:version(n) for n in ('numpy','scipy','numba','llvmlite','clarabel','torch','stable-baselines3')},
        timing_scope='shared cloud engineering observation; no OS scheduling/WCET guarantee')
    a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)


if __name__=='__main__':main()
