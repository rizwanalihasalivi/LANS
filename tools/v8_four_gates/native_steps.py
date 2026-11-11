"""Build/load the equivalent native Driver call loop; never integrate in Python."""
from pathlib import Path
import ctypes,subprocess,math


ROOT=Path(__file__).resolve().parents[2]
WEBOTS=ROOT/'integrations/webots/.runtime/webots'


def build(output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    command=['cc','-O2','-fPIC','-shared',str(Path(__file__).with_suffix('.c')),'-I'+str(WEBOTS/'include/controller/c'),'-L'+str(WEBOTS/'lib/controller'),'-Wl,-rpath,'+str(WEBOTS/'lib/controller'),'-ldriver','-lController','-lm','-o',str(output)]
    subprocess.run(command,check=True,capture_output=True,text=True);return command


class Steps:
    def __init__(self,path):
        self.library=ctypes.CDLL(str(path));self.call=self.library.lans_physical_steps
        self.call.argtypes=[ctypes.c_int,*([ctypes.c_double]*5),ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_double)];self.call.restype=ctypes.c_int
        self.output=(ctypes.c_double*4)();self.total_substeps=0
    def __call__(self,driver,left,right,command,cruise_target,actuator,previous_measured,substeps,physics_dt):
        done=self.call(substeps,physics_dt,command.steering,cruise_target,actuator,previous_measured,left._tag,right._tag,self.output)
        if done!=substeps:raise RuntimeError(f'native physical Driver loop failed status={done}')
        result=tuple(float(x) for x in self.output)
        if not all(math.isfinite(x) for x in result):raise ValueError('nonfinite native substep result')
        self.total_substeps+=done;return result
