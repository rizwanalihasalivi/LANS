import json,time
from pathlib import Path
import numpy as np
from worker import PolicyWorker

def main():
    root=Path(__file__).resolve().parents[1]
    worker=PolicyWorker(root/'results/research-training/full-0/policy.zip',delay_s=.1)
    try:
        assert worker.submit(np.zeros(9,dtype=np.float32),0)
        assert not worker.submit(np.zeros(9,dtype=np.float32),.01)
        assert worker.dropped_requests==1
        started=time.perf_counter();packet=None;poll_count=0;longest=0.
        while time.perf_counter()-started<10:
            before=time.perf_counter();early=worker.poll(.05);longest=max(longest,time.perf_counter()-before)
            assert early is None
            packet=worker.poll(.1);poll_count+=1
            if packet is not None:break
            time.sleep(.001)
        assert packet is not None and packet['sequence']==1 and packet['t_available_sim_s']==.1
        assert packet['inference_end_wall_s']>=packet['inference_start_wall_s']
        assert worker.submit(np.ones(9,dtype=np.float32)*.01,.11)
        result={'passed':True,'poll_count':poll_count,'maximum_measured_poll_wall_s':longest,'packet':packet,
                'checks':['one in flight','drop while busy','minimum simulated availability','wall inference timestamps','subsequent request accepted']}
        (root/'results/research-core/worker-test.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result))
    finally:worker.close()
if __name__=='__main__':main()
