"""Equivalent1ms C Driver loop and explicit startup-graph GC ablation."""
from pathlib import Path
import gc,json,os,sys,time,resource,traceback
import numpy as np
sys.path.insert(0,os.environ['LANS_ROOT'])


if __name__=='__main__':
    from vehicle import Driver
    from integrations.unified_lans.physics import Command,constrain
    from tools.v8_reliability import native_adapter as bridge
    from tools.v8_four_gates.fast_cost import EquivalentController
    from tools.v8_four_gates.resources import owned_affinity
    from tools.v8_four_gates.native_steps import Steps
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text());out=Path(case['output'])
    events=[];active=None;phase='startup';tick=None
    def observe_gc(kind,data):
        global active
        if kind=='start':active=(time.perf_counter(),time.process_time(),phase,tick,data['generation'])
        elif active:
            w,c,p,t,g=active;events.append(dict(phase=p,tick=t,generation=g,wall_ms=1000*(time.perf_counter()-w),cpu_ms=1000*(time.process_time()-c),collected=data['collected']));active=None
    class Warm(EquivalentController):
        def __init__(self,*a,**kw):
            super().__init__(*a,**kw);y,h,_=self.route.geometry(0.);z=np.array([0.,y+.3,h+.005,self.target_speed,0.,0.]);first=constrain(Command(self.baseline_fn(z,self.route),0.),self.issued,self.cfg)
            for planned in (False,True):
                self._candidate_cache={};self._cost_reference=None;self._plan=np.zeros(round(self.cfg.horizon/self.cfg.dt)) if planned else None;self._plan_residual=0. if planned else None
                self.cost(z.copy(),first,0.,0.,(),self.cfg.horizon)
            self._candidate_cache={};self._cost_reference=None;self._plan=None;self._plan_residual=None
        def decide(self,now,*a,**kw):
            global phase,tick
            old=phase;tick=round(now/self.cfg.dt);phase='owner' if old!='startup' else 'startup'
            try:return super().decide(now,*a,**kw)
            finally:phase='physics_and_logging' if old!='startup' else 'startup'
    class Startup:
        def __init__(self,driver):self.driver=driver;self.collected=False
        def __getattr__(self,name):return getattr(self.driver,name)
        def getTime(self):
            global phase
            if not self.collected:
                collected=gc.collect()
                if case['freeze_gc']:gc.freeze()
                self.collected=True;phase='measured'
                (out/'startup.json').write_text(json.dumps(dict(gc_collected=collected,gc_enabled=gc.isenabled(),freeze_count=gc.get_freeze_count(),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2)+'\n')
            return self.driver.getTime()
    bridge.Controller=Warm;bridge.control_affinity=owned_affinity;driver=Driver();gc.callbacks.append(observe_gc)
    steps=Steps(case['native_library']) if case['compiled_loop'] else None;status=0
    try:
        if steps is None:bridge.native_main(Startup(driver),case)
        else:bridge.native_main(Startup(driver),case,advance_physics=steps)
    except BaseException:
        (out/'failure.txt').write_text(traceback.format_exc());traceback.print_exc();status=1
    finally:
        phase='shutdown';gc.callbacks.remove(observe_gc)
        (out/'gc-profile.json').write_text(json.dumps(events,indent=2)+'\n')
        (out/'loop-metadata.json').write_text(json.dumps(dict(compiled_loop=steps is not None,measured_native_substeps=steps.total_substeps if steps else None,expected_native_substeps=round(case['duration']/.001),gc_enabled=gc.isenabled(),freeze_count=gc.get_freeze_count(),peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),indent=2)+'\n')
        if case['freeze_gc']:gc.unfreeze();gc.collect()
    driver.simulationQuit(status)
