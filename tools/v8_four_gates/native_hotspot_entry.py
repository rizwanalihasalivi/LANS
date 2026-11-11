"""Development-only cProfile/JIT/gain diagnostics of rare fast-owner spikes."""
import os,sys,json,cProfile,time,runpy
from pathlib import Path
sys.path.insert(0,os.environ['LANS_ROOT'])


if __name__=='__main__':
    from vehicle import Driver
    from numba.core import event
    from tools.v8_four_gates import fast_cost
    from tools.unified_control_v4.control import gain,gain_table
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text());out=Path(case['output']);slow=[];compiles=[];uid=0
    original=fast_cost.EquivalentController
    class Profile(original):
        def __init__(self,*a,**kw):
            global uid
            super().__init__(*a,**kw);uid+=1;self._profile_uid=uid
        def decide(self,now,*a,**kw):
            profiler=cProfile.Profile();g=gain.cache_info();gt=gain_table.cache_info();started=time.process_time();profiler.enable()
            try:return super().decide(now,*a,**kw)
            finally:
                profiler.disable();cpu_ms=1000*(time.process_time()-started)
                if cpu_ms>20.:
                    stats=profiler.getstats();stats.sort(key=lambda x:x.inlinetime,reverse=True)
                    slow.append(dict(controller=self._profile_uid,time_s=now,cpu_ms=cpu_ms,gain_misses=gain.cache_info().misses-g.misses,table_misses=gain_table.cache_info().misses-gt.misses,
                        calls=[dict(function=str(x.code),calls=x.callcount,own_s=x.inlinetime,total_s=x.totaltime) for x in stats[:25]]))
    class Compilation(event.Listener):
        def __init__(self):self.pending=[]
        def on_start(self,e):self.pending.append((time.perf_counter(),str(e.data.get('dispatcher'))))
        def on_end(self,e):
            if self.pending:
                w,n=self.pending.pop();compiles.append(dict(function=n,wall_ms=1000*(time.perf_counter()-w)))
    fast_cost.EquivalentController=Profile;quit_original=Driver.simulationQuit
    def quit_driver(self,status):
        (out/'owner-hotspots.json').write_text(json.dumps(slow,indent=2)+'\n');(out/'jit-events.json').write_text(json.dumps(compiles,indent=2)+'\n');return quit_original(self,status)
    Driver.simulationQuit=quit_driver
    with event.install_listener('numba:compile',Compilation()):runpy.run_module('tools.v8_four_gates.native_loop_entry',run_name='__main__')
