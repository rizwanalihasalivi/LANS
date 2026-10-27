"""Versioned hardening; do not mutate frozen v8/v9 evidence or policy ABI."""
import boot10
import math
import numbers
import types
from recovery8 import RecoveryController
from rollout10 import rk_cost
import numpy as np
from features9 import QueryController

class AuditedController(QueryController):
    choose_core=RecoveryController.choose
    def __init__(self,**kwargs):super().__init__(**kwargs);self.identity=None
    def submit(self,t,residual,service):
        if not all(math.isfinite(x) for x in (t,residual,service)) or t<0 or service<0:
            raise ValueError('Finite nonnegative request timestamp/service and finite residual required')
        if abs(residual)>.08+1e-9:raise ValueError('Out-of-bound residual must not be silently clipped')
        return super().submit(t,residual,service)
    def choose(self,t,baseline,estimate,actuator,speed,curvature,gain):
        # Invalid baseline is a control-system fault, not a usable fallback.
        if not math.isfinite(baseline) or abs(baseline)>.5+1e-9:raise ValueError('Invalid baseline; no valid fallback command available')
        if self.packet is not None:
            try:seq,observed,residual=self.packet
            except (ValueError,TypeError):return self.revoke(baseline,'packet_format')
            if isinstance(seq,(bool,np.bool_)) or not isinstance(seq,numbers.Integral) or seq<1:
                return self.revoke(baseline,'packet_identifier')
            if not all(isinstance(x,numbers.Real) and math.isfinite(x) for x in (observed,residual)) or observed<0:
                return self.revoke(baseline,'packet_timestamp_or_value')
            if self.identity is not None:
                last,stamp,value=self.identity
                if seq<last or (seq==last and (observed!=stamp or residual!=value)):
                    return self.revoke(baseline,'packet_identity')
            self.identity=(int(seq),observed,residual)
        if not math.isfinite(speed) or speed<5:return self.revoke(baseline,'speed_domain')
        if not math.isfinite(actuator) or abs(actuator)>.5+1e-9:return self.revoke(baseline,'actuator_domain')
        if self.baseline_only:return self.revoke(baseline,'baseline')
        return self.choose_core(t,baseline,estimate,actuator,speed,curvature,gain)

# Rebind only the isolated nominal numerical model; validity/recovery code is identical.
_core=RecoveryController.choose
class RKController(AuditedController):
    choose_core=types.FunctionType(_core.__code__,dict(_core.__globals__,expiry_cost=rk_cost),name='choose_core',argdefs=_core.__defaults__,closure=_core.__closure__)
