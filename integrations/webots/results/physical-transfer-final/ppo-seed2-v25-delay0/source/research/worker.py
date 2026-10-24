"""One in-flight CPU inference process. The control loop never waits for an action."""
import multiprocessing as mp
import queue
import time


def _run(model_path,requests,responses):
    try:
        import torch
        from stable_baselines3 import PPO
        torch.set_num_threads(1)
        model=PPO.load(model_path,device='cpu')
        responses.put(('ready',None))
        while True:
            request=requests.get()
            if request is None:return
            sequence,t_observation,observation=request
            started=time.perf_counter();action,_=model.predict(observation,deterministic=True);finished=time.perf_counter()
            responses.put(('output',dict(sequence=sequence,t_observation_s=t_observation,angle_rad=float(action[0])*.5,
                                         inference_start_wall_s=started,inference_end_wall_s=finished)))
    except Exception as error:
        responses.put(('error',repr(error)))


class PolicyWorker:
    def __init__(self,model_path,delay_s=0):
        context=mp.get_context('spawn')
        self.requests=context.Queue(maxsize=1);self.responses=context.Queue(maxsize=1)
        self.process=context.Process(target=_run,args=(str(model_path),self.requests,self.responses),daemon=True)
        self.process.start();status,message=self.responses.get(timeout=60)
        if status!='ready':raise RuntimeError(message)
        self.delay=delay_s;self.sequence=0;self.busy=False;self.pending=None;self.dropped_requests=0
    def submit(self,observation,t_sim):
        if self.busy:self.dropped_requests+=1;return False
        if not self.process.is_alive():raise RuntimeError('inference worker exited')
        self.sequence+=1;self.requests.put_nowait((self.sequence,t_sim,observation.copy()));self.busy=True;return True
    def poll(self,t_sim):
        if self.pending is None:
            try:
                status,message=self.responses.get_nowait()
            except queue.Empty:
                if not self.process.is_alive():raise RuntimeError('inference worker exited')
                return None
            if status=='error':raise RuntimeError(message)
            self.pending=message
        if t_sim+1e-9<self.pending['t_observation_s']+self.delay:return None
        result=self.pending;result['t_available_sim_s']=t_sim
        self.pending=None;self.busy=False
        return result
    def close(self):
        try:self.requests.put_nowait(None)
        except queue.Full:pass
        self.process.join(timeout=2)
        if self.process.is_alive():self.process.terminate();self.process.join(timeout=2)
        self.requests.close();self.responses.close()
