"""Unchanged-law fast-kernel/resource diagnostic; startup work is explicit."""
from pathlib import Path
import gc,json,os,sys,time,traceback
import numpy as np

sys.path.insert(0,os.environ['LANS_ROOT'])


if __name__=='__main__':
    from vehicle import Driver
    from integrations.unified_lans.physics import Command,constrain
    from tools.v8_reliability import native_adapter as bridge
    from tools.v8_four_gates.fast_cost import EquivalentController
    from tools.v8_four_gates.resources import owned_affinity
    from threadpoolctl import threadpool_info
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text());out=Path(case['output'])
    selected=EquivalentController if case['fast_kernel'] else bridge.Controller
    class Warm(selected):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw);y,h,_=self.route.geometry(0.);z=np.array([0.,y+.3,h+.005,self.target_speed,0.,0.])
            first=constrain(Command(self.baseline_fn(z,self.route),0.),self.issued,self.cfg)
            for planned in (False,True):
                self._candidate_cache={};self._cost_reference=None;self._plan=np.zeros(round(self.cfg.horizon/self.cfg.dt)) if planned else None;self._plan_residual=0. if planned else None
                self.cost(z.copy(),first,0.,0.,(),self.cfg.horizon)
            self._candidate_cache={};self._cost_reference=None;self._plan=None;self._plan_residual=None
    class Startup:
        def __init__(self,driver):self.driver=driver;self.collected=False
        def __getattr__(self,name):return getattr(self.driver,name)
        def getTime(self):
            if not self.collected:
                start=time.perf_counter();n=gc.collect();self.collected=True
                (out/'explicit-startup.json').write_text(json.dumps(dict(gc_collected=n,gc_wall_s=time.perf_counter()-start,optional_plan_cost_warmed=True,
                    affinity_cpus=os.environ.get('LANS_RUNTIME_CPUS'),lp_num_threads=os.environ.get('LP_NUM_THREADS'),blas_pools=threadpool_info()),indent=2)+'\n')
            return self.driver.getTime()
    bridge.Controller=Warm
    if case['resources']:bridge.control_affinity=owned_affinity
    driver=Driver()
    try:bridge.native_main(Startup(driver),case)
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)
