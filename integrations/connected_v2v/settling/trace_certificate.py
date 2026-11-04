"""Exact finite-trace separating-axis certificates with continuous bridge bounds.

This is A POSTERIORI verification, not a prospective full-controller theorem.
Assumptions: poses enclose actual samples; planar bodies fit declared rectangles;
|Cartesian coordinate acceleration|<=A and |yaw rate|<=O between endpoints.
The bridge inequality proves continuous separation between logged samples.
Sin/cos enclosures use fixed-point interval Taylor arithmetic, not floating trig.
"""
from fractions import Fraction as F
from functools import lru_cache
import math

Q=10**18
AXIS=10**6
UM=10**6
L=F('2.6');W=F('1.1')
A=F(20);OMEGA=F(2);POSE=F('.02')


def ceil_frac(z):return -((-z.numerator)//z.denominator)
def integer_up(z,scale=UM):return ceil_frac(z*scale)
def integer_down(z,scale=UM):return (z*scale).numerator//(z*scale).denominator
def mul(x,y):
    values=[a*b for a in x for b in y]
    return min(values)//Q,-((-max(values))//Q)
def divide(x,k):return x[0]//k,-((-x[1])//k)
def negate(x):return -x[1],-x[0]
def add(x,y):return x[0]+y[0],x[1]+y[1]
def absolute(x):return max(abs(x[0]),abs(x[1]))


@lru_cache(maxsize=32768)
def trig_bounds(theta):
    angle=F(str(theta))
    if abs(angle)>4:raise ValueError('heading outside Taylor contract [-4,4]')
    x=(integer_down(angle,Q),integer_up(angle,Q));xx=mul(x,x)
    sine=term=x
    for k in range(1,13):
        term=negate(divide(mul(term,xx),(2*k)*(2*k+1)));sine=add(sine,term)
    cosine=term=(Q,Q)
    for k in range(1,13):
        term=negate(divide(mul(term,xx),(2*k-1)*(2*k)));cosine=add(cosine,term)
    es=integer_up(F(4**27,math.factorial(27)),Q)
    ec=integer_up(F(4**26,math.factorial(26)),Q)
    return (sine[0]-es,sine[1]+es),(cosine[0]-ec,cosine[1]+ec)


def scale_interval(x,k):
    return (x[0]*k,x[1]*k) if k>=0 else (x[1]*k,x[0]*k)


def support_upper(theta,nx,ny):
    sn,cs=trig_bounds(theta)
    tangent=add(scale_interval(cs,nx),scale_interval(sn,ny))
    normal=add(scale_interval(sn,-nx),scale_interval(cs,ny))
    return (L*absolute(tangent)+W*absolute(normal))/(Q*AXIS)


def certificate(a0,a1,b0,b1,h):
    """Pose triples x,y,heading; return an exact integer separating witness."""
    h=F(str(h));aa=[tuple(F(str(v)) for v in z) for z in (a0,a1)]
    bb=[tuple(F(str(v)) for v in z) for z in (b0,b1)]
    # Trigonometry here chooses a rational direction only. Any nonzero rational
    # direction is valid; safety calculations below use interval/exact arithmetic.
    for heading in (a0[2],b0[2],a1[2],b1[2]):
        for normal in (False,True):
            angle=float(heading)+(math.pi/2 if normal else 0.)
            nx,ny=round(math.cos(angle)*AXIS),round(math.sin(angle)*AXIS)
            if nx==ny==0:continue
            delta=[F(nx,AXIS)*(b[0]-a[0])+F(ny,AXIS)*(b[1]-a[1]) for a,b in zip(aa,bb)]
            if max(delta)<0:nx,ny=-nx,-ny;delta=[-z for z in delta]
            if min(delta)<=0:continue
            norm=F(abs(nx)+abs(ny),AXIS)
            ra=max(support_upper(z[2],nx,ny) for z in (a0,a1))
            rb=max(support_upper(z[2],nx,ny) for z in (b0,b1))
            # At every t, use the nearer endpoint's heading. Rotation support
            # change <=(L+W)*||n||_1*Omega*h/2 per body. Each center's deviation
            # from the endpoint chord is <=A*h²/8 per Cartesian coordinate.
            rotation=(L+W)*norm*OMEGA*h
            bridge=norm*A*h*h/4
            pose=2*norm*POSE
            lower=integer_down(min(delta));upper=integer_up(ra+rb+rotation+bridge+pose)
            if lower>upper:
                return dict(axis=[nx,ny],separation_lower_um=lower,occupancy_upper_um=upper,
                    margin_um=lower-upper)
    return None
