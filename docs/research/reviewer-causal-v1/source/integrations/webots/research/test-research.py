import unittest
import numpy as np
from core import Sensor,Supervisor,GAINS
from comparison import configure_lqr
from tracking import equilibrium,tracking_lqr
from geometry import corridor_margin

configure_lqr()

class ResearchContracts(unittest.TestCase):
    def test_curvature_equilibrium_command(self):
        for speed in (15,20,25):
            for curvature in (-.001,.001):
                target=equilibrium(speed,curvature)
                command=tracking_lqr(target,speed,curvature)
                expected=(2.6+1650/2.6*(1.4/80000-1.2/80000)*speed**2)*curvature
                self.assertAlmostEqual(command,expected)
                vy,r=target[1],target[3]
                fyf=80000*(command-(vy+1.2*r)/speed)
                fyr=80000*(-(vy-1.4*r)/speed)
                self.assertAlmostEqual((fyf+fyr)/1650-speed*r,0.,places=10)
                self.assertAlmostEqual((1.2*fyf-1.4*fyr)/4224,0.,places=10)
                self.assertAlmostEqual(vy+speed*target[2],0.)
    def test_delayed_sensor_does_not_leak_new_lateral_position(self):
        path=(0,0.,120.,0.);state=np.zeros(6)
        fresh=Sensor(9000,noise=0);delayed=Sensor(9000,noise=0,delay_steps=1)
        fresh.measure(state,20,path);delayed.measure(state,20,path)
        state[1]=.2
        a=fresh.measure(state,20,path)[1];b=delayed.measure(state,20,path)[1]
        self.assertGreater(a[0],.1);self.assertAlmostEqual(b[0],0.)
        c=delayed.measure(state,20,path)[1];self.assertGreater(c[0],.1)
    def test_seeded_sensor_repeatability(self):
        a,b=Sensor(901),Sensor(901);state=np.zeros(6);path=(0,1.,120.,0.)
        for i in range(100):
            state[0]=i*.2
            np.testing.assert_array_equal(a.measure(state,20,path)[0],b.measure(state,20,path)[0])
    def test_invalid_outputs_and_recovery(self):
        sup=Supervisor();state=np.zeros(4)
        for i in range(30):command,w,_=sup.fuse(i*.01,.02,(i,i*.01,.1),state)
        self.assertGreater(w,0)
        for packet in ((30,.31,float('nan')),(30,.5,.1),(30,0.,.1),(0,.31,.1)):
            command,w,_=sup.fuse(.31,.02,packet,state);self.assertEqual(command,.02);self.assertEqual(w,0)
        command,w,_=sup.fuse(.32,.02,(31,.32,.1),state);self.assertEqual(w,0)
    def test_vehicle_footprint_corridor(self):
        path=(0,0.,120.,0.)
        self.assertAlmostEqual(corridor_margin(0,0,0,path),.85)
        self.assertAlmostEqual(corridor_margin(0,1.,0,path),-.15)

if __name__=='__main__':unittest.main()
