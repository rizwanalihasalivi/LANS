from functools import lru_cache
import math
import numpy as np
from scipy.linalg import solve_continuous_are
from models.bicycle_model import VEHICLE_PARAMS,get_error_state_model
from integrations.unified_lans.physics import Command,advance,constrain,errors,clip_scalar
from integrations.unified_lans.controller import Pipeline
from integrations.unified_lans.traffic import Supervisor,extrapolate
from .kernels import rollout,step

GRID=(-.08,-.04,-.02,-.01,-.005,-.0025,0.,.0025,.005,.01,.02,.04,.08)


@lru_cache(maxsize=1024)
def gain(speed,penalty,stiffness=1.):
    params=dict(VEHICLE_PARAMS);params['Cf']*=stiffness;params['Cr']*=stiffness
    a,b=get_error_state_model(speed,params)
    p=solve_continuous_are(a,b,np.diag([1.,.1,1.,.1]),np.array([[penalty]]))
    return (b.T@p/penalty).ravel()


@lru_cache(maxsize=64)
def gain_table(penalty,stiffness):
    return np.array([gain(max(2.,i/2),penalty,stiffness) for i in range(65)])


class ScheduledLQR:
    def __init__(self,penalty=1.):self.penalty=float(penalty);self.stiffness=1.
    def __call__(self,state,route):
        v=max(2.,float(state[3]));scheduled=max(2.,round(v*2)/2)
        e,k=errors(state,route);p=dict(VEHICLE_PARAMS);p['Cf']*=self.stiffness;p['Cr']*=self.stiffness;l=p['lf']+p['lr']
        vy=(p['lr']*v-p['m']*p['lf']*v**3/(l*p['Cr']))*k
        target=np.array([0.,0.,-vy/v,0.])
        feedforward=(l+p['m']/l*(p['lr']/p['Cf']-p['lf']/p['Cr'])*v*v)*k
        return float(clip_scalar(feedforward-gain(scheduled,self.penalty,self.stiffness)@(e-target),-.5,.5))


class StopSupervisor(Supervisor):
    def __init__(self,cfg,scenario):super().__init__(cfg,scenario);self.force_stop=False
    def assess(self,*args,**kwargs):
        risk=super().assess(*args,**kwargs)
        if self.force_stop:risk.state='DANGER';self.state='DANGER'
        return risk


class Controller(Pipeline):
    """Same limits/TTLs; bounded dead reckoning is for braking, never PPO admission."""
    def __init__(self,*args,penalty=1.,adaptive=False,corridor=True,backup=True,mpc=False,**kwargs):
        if not corridor:raise ValueError('corridor eligibility is mandatory in v4')
        if kwargs.get('deterministic_grid'):
            kwargs['deterministic_grid']=tuple(sorted(set(kwargs['deterministic_grid'])|set(GRID)))
        self.stiffness_estimate=1.;self.adaptive=adaptive;self.corridor=corridor;self.backup=backup
        self.backup_limit_s=2.5;self._previous_measurement=None
        self._id_grid=np.linspace(.7,1.3,25);self._id_scores=np.zeros(25);self._id_weight=0.;self._id_steps=0
        self.stiffness_uncertainty=.3
        super().__init__(*args,baseline_fn=ScheduledLQR(penalty),predict_fn=self.predict,**kwargs)
        self.supervisor=StopSupervisor(self.cfg,self.supervisor.scenario)
        self._gains=gain_table(float(penalty),1.);self.feedback_stiffness=1.
        kind={'straight':0,'sine':1,'lane_change':2}[self.route.kind]
        self._route=np.array([kind,getattr(self.route,'mirror',1),getattr(self.route,'phase',0.),getattr(self.route,'amplitude',1.)],float)
        self._cost_reference=None
        self._base_grid=self.deterministic_grid;self._plan=None;self._plan_residual=None
        if mpc:
            from .mpc import Planner
            self.planner=Planner()
        else:self.planner=None

    def predict(self,z,command,dt):
        return advance(z,command,dt,self.stiffness_estimate if self.adaptive else 1.)

    def update_model(self):
        current=self.inbox.latest.get('ego');old=self._previous_measurement
        if current is None or old is not None and current.sequence==old.sequence:return
        self._previous_measurement=current
        if not self.adaptive or old is None:return
        dt=current.observed_s-old.observed_s
        if abs(dt-self.cfg.dt)>1e-8:return
        commands=[c for start,end,c in self.history if abs(start-old.observed_s)<1e-8 and abs(end-current.observed_s)<1e-8]
        if len(commands)!=1:return
        a=np.array(old.state);b=np.array(current.state)
        if min(a[3],b[3])<2.:return
        u=commands[0]
        # Use the same discrete applied-input integration as the plant, not a
        # biased finite-difference/trapezoidal continuous-time regression.
        predicted=np.array([step(a,u.steering,u.accel,dt,k)[4:] for k in self._id_grid])
        errors_=np.sum((predicted-b[None,4:])**2,axis=1)
        if np.ptp(errors_)<1e-10:return
        if errors_.min()>1e-3:
            self.stiffness_uncertainty=.3;return
        self._id_scores=.98*self._id_scores+errors_;self._id_weight=.98*self._id_weight+1;self._id_steps+=1
        losses=self._id_scores/self._id_weight;index=int(np.argmin(losses))
        estimate=self._id_grid[index]
        if 0<index<len(losses)-1:
            left,middle,right=losses[index-1:index+2];curvature=left-2*middle+right
            if curvature>1e-16:estimate+=.025*float(clip_scalar(.5*(left-right)/curvature,-1,1))
        self.stiffness_estimate=float(clip_scalar(estimate,.7,1.3))
        compatible=self._id_grid[losses<=losses.min()+1e-8]
        self.stiffness_uncertainty=max(.025,float(np.max(abs(compatible-self.stiffness_estimate)))) if self._id_steps>=6 else .3
        self.feedback_stiffness=float(clip_scalar(round(self.stiffness_estimate*20)/20,.7,1.3))
        self.baseline_fn.stiffness=self.feedback_stiffness
        self._gains=gain_table(self.baseline_fn.penalty,self.feedback_stiffness)

    def reconstruct(self,now):
        packet=self.inbox.latest.get('ego')
        if packet is None:return None
        age=now-packet.observed_s
        limit=self.backup_limit_s if self.backup else self.cfg.ego_ttl
        if age>limit+1e-9:return None
        z=np.array(packet.state);cursor=packet.observed_s
        for start,end,command in self.history:
            if end<=cursor+1e-10:continue
            if start>cursor+1e-8:return None
            until=min(end,now)
            if until>cursor:z=self.predict(z,command,until-cursor);cursor=until
            if cursor>=now-1e-9:break
        return z if cursor>=now-1e-8 else None

    def features(self,now,busy=False):
        p=self.inbox.latest.get('ego')
        if p is None or now-p.observed_s>self.cfg.ego_ttl+1e-9:return None
        return super().features(now,busy)

    def cost(self,z,first,residual,accel,vehicles,lifetime):
        cfg=self.cfg
        center=self.stiffness_estimate if self.adaptive else 1.
        width=self.stiffness_uncertainty
        models=np.array([max(.7,center-width),center,min(1.3,center+width)]) if self.adaptive else np.array([.7,1.,1.3])
        npcs=np.array([[*other,uncertainty] for _,other,uncertainty in vehicles],float).reshape(-1,7)
        args=(self.issued.steering,cfg.dt,cfg.horizon,self._gains,self._route,npcs,cfg.vehicle_radius,cfg.buffer,cfg.uncertainty_rate,cfg.steering_limit,cfg.steering_rate)
        def values(steering,plan=None):
            return np.array([rollout(z,steering,accel,args[0],args[1],args[2],s,*args[3:],self.feedback_stiffness,plan) for s in models])
        base=constrain(Command(self.baseline_fn(z,self.route),accel),self.issued,cfg)
        key=(tuple(z),accel,self.issued.steering,center,width,tuple(npcs.ravel()))
        if self._cost_reference is None or self._cost_reference[0]!=key:
            self._cost_reference=(key,values(base.steering))
        reference=self._cost_reference[1]
        planned=self._plan is not None and self._plan_residual is not None and abs(residual-self._plan_residual)<1e-12
        result=values(first.steering,self._plan) if planned else (reference if first.steering==base.steering else values(first.steering))
        margin=float(result[:,1].min())
        if first.steering!=base.steering or planned:
            # Accept only robust predicted improvements, with explicit heading/rate budgets.
            if (np.any(result[:,0]>=reference[:,0]-1e-9)
                or np.any(result[:,2]>1.21*reference[:,2]+2e-6)
                or np.any(result[:,3]>1.21*reference[:,3]+1e-5)):
                margin=min(margin,-1e-9)
        return float(result[:,0].mean()),margin

    def decide(self,now,worker_failed=False):
        self._cost_reference=None
        self.update_model();p=self.inbox.latest.get('ego')
        stale=p is None or now-p.observed_s>self.cfg.ego_ttl+1e-9
        self.supervisor.force_stop=stale
        self.deterministic_grid=self._base_grid;self._plan=None;self._plan_residual=None
        if self.planner is not None and not stale and not worker_failed:
            z=self.forecast(now)
            if z is not None:
                previous_risk=self.supervisor.state
                risk=self.supervisor.assess(z,self.inbox,self.expected,now,now+self.delay)
                self.supervisor.state=previous_risk
                if risk.state!='DANGER':
                    plan=self.planner.plan(z,self.route,self.issued.steering,self.cfg,self.feedback_stiffness,self.baseline_fn.penalty)
                    if plan is not None:
                        residual=float(clip_scalar(plan[0]-self.baseline_fn(z,self.route),-self.cfg.residual_limit,self.cfg.residual_limit))
                        if abs(residual)>1e-10:
                            self._plan=plan;self._plan_residual=residual
                            self.deterministic_grid=tuple(self._base_grid)+(residual,)
        result=super().decide(now,worker_failed=worker_failed or stale)
        if stale and result['source']!='hold_brake':
            result['source']='backup_lqr';result['reason']='bounded_dead_reckoning_brake'
        result.update(stiffness_estimate=self.stiffness_estimate,ego_backup=stale,
                      stiffness_uncertainty=self.stiffness_uncertainty,estimate_age=now-p.observed_s if p else None)
        result.update(planner_status=self.planner.status if self.planner else 'DISABLED',
            planner_failures=self.planner.failures if self.planner else 0,
            planned_candidate_selected=self._plan_residual is not None and abs(result['residual']-self._plan_residual)<1e-12)
        return result

    def apply(self,now,state,stiffness=1.):
        history=self.history.copy();result=super().apply(now,state,stiffness)
        history.append(self.history[-1]);self.history=[x for x in history if x[1]>=now-self.backup_limit_s-self.cfg.ego_ttl]
        return result
