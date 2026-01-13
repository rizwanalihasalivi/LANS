import numpy as np

def bicycle_model(vx, params):
    m = params["m"]
    Iz = params["Iz"]
    lf = params["lf"]
    lr = params["lr"]
    Cf = params["Cf"]
    Cr = params["Cr"]

    A = np.array([
        [-(Cf + Cr)/(m*vx),     (-Cf*lf + Cr*lr)/(m*vx) - vx,   0,  0],
        [(-Cf*lf + Cr*lr)/(Iz*vx), -(Cf*lf**2 + Cr*lr**2)/(Iz*vx), 0, 0],
        [1, 0, 0, vx],
        [0, 1, 0, 0]
    ])

    B = np.array([
        [Cf/m],
        [Cf*lf/Iz],
        [0],
        [0]
    ])

    return A, B

