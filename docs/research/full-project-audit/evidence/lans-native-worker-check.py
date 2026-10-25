import json,sys,time
import numpy as np
sys.path.insert(0,'/workspace/LANS-webots/integrations/webots/research')
from worker import PolicyWorker
if __name__=='__main__':
    worker=PolicyWorker('/workspace/LANS-webots/integrations/webots/results/research-training/full-0/policy.zip',.1)
    try:
        assert worker.submit(np.zeros(9,dtype=np.float32),0.)
        assert not worker.submit(np.zeros(9,dtype=np.float32),.01)
        started=time.monotonic();packet=None
        while time.monotonic()-started<10:
            assert worker.poll(.05) is None
            packet=worker.poll(.1)
            if packet:break
            time.sleep(.005)
        assert packet and packet['sequence']==1 and packet['t_available_sim_s']==.1
        assert worker.submit(np.ones(9,dtype=np.float32)*.01,.11)
    finally:worker.close()
    assert not worker.process.is_alive()
    print(json.dumps(dict(passed=True,one_inflight=True,minimum_simulated_delay=True,packet=packet,closed=True)))
