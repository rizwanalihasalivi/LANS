import ctypes,subprocess
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from integrations.unified_lans.physics import Command
from tools.v8_reliability.native_adapter import physical_steps
from .native_steps import Steps,WEBOTS


@pytest.fixture(scope='module')
def api(tmp_path_factory):
    folder=tmp_path_factory.mktemp('native-step-stub');stub=folder/'stub.c';output=folder/'stub.so'
    stub.write_text('''
#include <webots/vehicle/driver.h>
#include <webots/position_sensor.h>
static int n=0, stop=-1; static double angles[1000],speeds[1000];
void reset(int limit) { n=0; stop=limit; }
int count() { return n; }
double angle(int i) { return angles[i]; }
double speed(int i) { return speeds[i]; }
void wbu_driver_set_steering_angle(double a) { angles[n]=a; }
void wbu_driver_set_cruising_speed(double s) { speeds[n]=s; }
int wbu_driver_step() { if(n==stop) return -1; ++n; return 0; }
double wb_position_sensor_get_value(WbDeviceTag tag) { return .01*n+.001*tag; }
''')
    subprocess.run(['cc','-O2','-fPIC','-shared',str(Path(__file__).with_name('native_steps.c')),str(stub),'-I'+str(WEBOTS/'include/controller/c'),'-lm','-o',str(output)],check=True,capture_output=True)
    lib=ctypes.CDLL(str(output))
    for name in ('angle','speed'):
        f=getattr(lib,name);f.argtypes=[ctypes.c_int];f.restype=ctypes.c_double
    lib.wb_position_sensor_get_value.argtypes=[ctypes.c_int];lib.wb_position_sensor_get_value.restype=ctypes.c_double
    lib.wbu_driver_set_steering_angle.argtypes=[ctypes.c_double];lib.wbu_driver_set_cruising_speed.argtypes=[ctypes.c_double]
    return lib,output


@pytest.mark.parametrize('target,previous',[(-.2,0.),(.02,.1),(.4,-.1)])
def test_native_loop_preserves_every1ms_call_and_measurement(api,target,previous):
    lib,path=api;driver=SimpleNamespace(setSteeringAngle=lib.wbu_driver_set_steering_angle,setCruisingSpeed=lib.wbu_driver_set_cruising_speed,step=lib.wbu_driver_step)
    left=SimpleNamespace(_tag=12,getValue=lambda:lib.wb_position_sensor_get_value(12));right=SimpleNamespace(_tag=13,getValue=lambda:lib.wb_position_sensor_get_value(13))
    args=(driver,left,right,Command(target,0.),12.,previous,0.,50,.001)
    lib.reset(-1);expected=physical_steps(*args);angles=[lib.angle(i) for i in range(50)];speeds=[lib.speed(i) for i in range(50)];assert lib.count()==50
    lib.reset(-1);advance=Steps(path);actual=advance(*args)
    assert lib.count()==advance.total_substeps==50
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal([lib.angle(i) for i in range(50)],angles)
    np.testing.assert_array_equal([lib.speed(i) for i in range(50)],speeds)


def test_native_loop_preserves_early_simulator_stop(api):
    lib,path=api;lib.reset(7);advance=Steps(path)
    with pytest.raises(RuntimeError,match='status=-1'):advance(None,SimpleNamespace(_tag=12),SimpleNamespace(_tag=13),Command(.1,0.),12.,0.,0.,50,.001)
    assert lib.count()==7 and advance.total_substeps==0
