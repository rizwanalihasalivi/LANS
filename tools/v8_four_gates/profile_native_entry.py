"""Development-only GC/JIT/gain/phase profiling around unchanged native owners."""
from contextlib import ExitStack
from pathlib import Path
import gc,json,os,sys,time,resource

sys.path.insert(0,os.environ['LANS_ROOT'])


class Collector:
    def __init__(self):self.tick=None;self.phase=None;self.garbage=[];self.compiles=[];self.rows=[];self.pools=[];self.active_gc=None;self.uid=0
    def gc_callback(self,kind,data):
        if kind=='start':self.active_gc=(time.perf_counter(),time.process_time(),self.tick,self.phase,data['generation'])
        elif self.active_gc is not None:
            w,c,t,p,g=self.active_gc;self.garbage.append(dict(tick=t,phase=p,generation=g,wall_ms=1000*(time.perf_counter()-w),cpu_ms=1000*(time.process_time()-c),collected=data['collected']));self.active_gc=None


def install(collector):
    from threadpoolctl import threadpool_info
    from tools.unified_control_v4.control import gain,gain_table
    from tools.v8_reliability import native_adapter as bridge
    from numba.core import event
    class Compilation(event.Listener):
        def __init__(self):self.pending=[]
        def on_start(self,e):self.pending.append((time.perf_counter(),time.process_time(),collector.tick,collector.phase,str(e.data.get('dispatcher'))))
        def on_end(self,e):
            if self.pending:
                w,c,t,p,n=self.pending.pop();collector.compiles.append(dict(tick=t,phase=p,function=n,wall_ms=1000*(time.perf_counter()-w),cpu_ms=1000*(time.process_time()-c)))
    class Observe:
        def __init__(self,*a,**kw):
            self._phase_stats={};super().__init__(*a,**kw);collector.uid+=1;self._uid=collector.uid
            collector.pools.append(dict(controller=self._uid,pools=threadpool_info()))
            if self.planner is not None:
                original=self.planner.plan
                def planning(*a,**kw):return self._measure('plan_or_response_projection',original,*a,**kw)
                self.planner.plan=planning
        def _measure(self,name,fn,*a,**kw):
            old=collector.phase;collector.phase=name;w=time.perf_counter();c=time.process_time()
            try:return fn(*a,**kw)
            finally:
                stat=self._phase_stats.setdefault(name,dict(calls=0,wall_ms=0.,cpu_ms=0.));stat['calls']+=1;stat['wall_ms']+=1000*(time.perf_counter()-w);stat['cpu_ms']+=1000*(time.process_time()-c);collector.phase=old
        def update_model(self):return self._measure('model_update',super().update_model)
        def cost(self,*a,**kw):return self._measure('admission_cost',super().cost,*a,**kw)
        def decide(self,now,*a,**kw):
            collector.tick=dict(controller=self._uid,time_s=now);self._phase_stats={};old=collector.phase;collector.phase='owner_decision';g=gain.cache_info();gt=gain_table.cache_info();before=resource.getrusage(resource.RUSAGE_SELF)
            w=time.perf_counter();c=time.process_time()
            try:return super().decide(now,*a,**kw)
            finally:
                after=resource.getrusage(resource.RUSAGE_SELF);collector.rows.append(dict(controller=self._uid,time_s=now,wall_ms=1000*(time.perf_counter()-w),cpu_ms=1000*(time.process_time()-c),phases=self._phase_stats,
                    gain_cache_misses=gain.cache_info().misses-g.misses,gain_table_misses=gain_table.cache_info().misses-gt.misses,
                    minor_faults=after.ru_minflt-before.ru_minflt,major_faults=after.ru_majflt-before.ru_majflt));collector.tick=None;collector.phase=old
    class New(Observe,bridge.Controller):pass
    class Sync(Observe,bridge.Synchronous):pass
    class Old(Observe,bridge.OriginalV8):pass
    bridge.Controller=New;bridge.Synchronous=Sync;bridge.OriginalV8=Old
    return bridge,event.install_listener('numba:compile',Compilation())


if __name__=='__main__':
    from vehicle import Driver
    import traceback
    case=json.loads(Path(os.environ['LANS_CASE_CONFIG']).read_text());out=Path(case['output']);collector=Collector();bridge,listener=install(collector);driver=Driver()
    gc.callbacks.append(collector.gc_callback)
    try:
        with listener:bridge.native_main(driver,case)
    except BaseException:
        (out/'profile-failure.txt').write_text(traceback.format_exc());traceback.print_exc();driver.simulationQuit(1)
    else:driver.simulationQuit(0)
    finally:
        gc.callbacks.remove(collector.gc_callback)
        (out/'owner-phase-profile.json').write_text(json.dumps(collector.rows,indent=2)+'\n')
        (out/'gc-profile.json').write_text(json.dumps(collector.garbage,indent=2)+'\n')
        (out/'jit-profile.json').write_text(json.dumps(collector.compiles,indent=2)+'\n')
        (out/'threadpool-profile.json').write_text(json.dumps(collector.pools,indent=2)+'\n')
