"""Lifecycle and evidence regressions; no Webots process needed."""
import importlib.util,json,queue,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from worker import PolicyWorker
HERE=Path(__file__).resolve().parent

class FakeQueue:
    def __init__(self,result=None,error=None):self.result=result;self.error=error;self.closed=False
    def get(self,timeout=None):
        if self.error:raise self.error
        return self.result
    def put_nowait(self,value):pass
    def close(self):self.closed=True
class FakeProcess:
    pid=1
    def __init__(self):self.alive=True;self.terminated=False
    def start(self):pass
    def join(self,timeout=None):pass
    def is_alive(self):return self.alive
    def terminate(self):self.terminated=True;self.alive=False
class FakeContext:
    def __init__(self,result=None,error=None):
        self.queues=[FakeQueue(),FakeQueue(result,error)];self.index=0;self.process=FakeProcess()
    def Queue(self,maxsize):q=self.queues[self.index];self.index+=1;return q
    def Process(self,**kwargs):return self.process

class NativeBoundaries(unittest.TestCase):
    def test_startup_errors_clean_up_process_and_queues(self):
        for ctx in [FakeContext(('error','bad checkpoint')),FakeContext(error=queue.Empty())]:
            with self.subTest(error=ctx.queues[1].error),patch('worker.mp.get_context',return_value=ctx):
                with self.assertRaises((RuntimeError,queue.Empty)):PolicyWorker('unused')
                self.assertTrue(ctx.process.terminated)
                self.assertTrue(all(q.closed for q in ctx.queues))
    def test_invalid_delay_rejected_before_spawn(self):
        for delay in [-.1,float('nan'),float('inf')]:
            with patch('worker.mp.get_context') as constructor:
                with self.assertRaises(ValueError):PolicyWorker('unused',delay)
                constructor.assert_not_called()
    def test_closed_worker_and_nonfinite_sim_time(self):
        ctx=FakeContext(('ready',None))
        with patch('worker.mp.get_context',return_value=ctx):
            worker=PolicyWorker('unused')
            for method in [lambda:worker.poll(float('nan')),lambda:worker.submit(np.zeros(9),float('inf'))]:
                with self.assertRaises(ValueError):method()
            worker.close();worker.close()
            with self.assertRaises(RuntimeError):worker.submit(np.zeros(9),0.)
            with self.assertRaises(RuntimeError):worker.poll(0.)
    def test_same_case_name_in_distinct_outputs_has_distinct_worlds(self):
        spec=importlib.util.spec_from_file_location('physical_runner',HERE/'run-physical.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            module.ROOT=Path(temp);(module.ROOT/'controllers').mkdir()
            first=module.create_case_project(Path(temp)/'run-a'/'same-case')
            second=module.create_case_project(Path(temp)/'run-b'/'same-case')
            self.assertNotEqual(first,second)
            self.assertTrue((first/'controllers').is_symlink())
            self.assertTrue((second/'worlds').is_dir())

    def test_timeout_terminates_launcher_descendants(self):
        import os,subprocess,time
        from native_process import run_native
        command=[sys.executable,'-c',"import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"]
        with tempfile.TemporaryFile(mode='w+') as output:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_native(command,env=os.environ.copy(),stdout=output,timeout=.3)
            output.seek(0);child=int(output.read().strip())
            for _ in range(100):
                status=Path(f'/proc/{child}/stat')
                if not status.exists() or status.read_text().split()[2]=='Z':break
                time.sleep(.01)
            else:self.fail('timed-out native descendant is still running')

    def test_held_packet_counted_once_for_inference_timing(self):
        spec=importlib.util.spec_from_file_location('physical_audit',HERE/'analyze-physical.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        rows=[dict(ppo_available=1,t_observation_s=1.,inference_wall_s=.1)]*10
        rows+=[dict(ppo_available=1,t_observation_s=2.,inference_wall_s=.01)]
        self.assertEqual(module.inference_durations(rows),[.1,.01])

    def test_native_metrics_recomputed_from_raw_evidence(self):
        spec=importlib.util.spec_from_file_location('physical_audit',HERE/'analyze-physical.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fixture=HERE.parent/'results/physical-validated/open-v15-d0.0'
        # Copy a known native fixture without touching archived evidence.
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'fixture';shutil.copytree(fixture,target)
            module.audit(target)
            metric=target/'metrics.json';value=json.loads(metric.read_text());value['rmse_m']+=.1;metric.write_text(json.dumps(value))
            with self.assertRaisesRegex(AssertionError,'RMSE disagrees'):module.audit(target)

if __name__=='__main__':unittest.main()
