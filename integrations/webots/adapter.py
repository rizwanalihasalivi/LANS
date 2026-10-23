"""Full front road-wheel command adapter; SI units, positive left, no LANS policy."""
import math


class VehicleAdapter:
    def __init__(self, driver, steering_limit_rad=0.5):
        if not math.isfinite(steering_limit_rad) or not 0 < steering_limit_rad <= 0.5:
            raise ValueError('steering limit must be in (0, 0.5] rad')
        self.driver = driver
        self.limit = steering_limit_rad
        self.node = driver.getSelf()
        self.left = driver.getDevice('left_steer_sensor')
        self.right = driver.getDevice('right_steer_sensor')
        period_ms = int(driver.getBasicTimeStep())
        self.left.enable(period_ms)
        self.right.enable(period_ms)

    def command(self, steering_rad, speed_m_s):
        if not all(math.isfinite(v) for v in (steering_rad, speed_m_s)):
            raise ValueError('nonfinite vehicle command')
        if speed_m_s < 0:
            raise ValueError('reverse driving is not supported by this adapter')
        applied = max(-self.limit, min(self.limit, steering_rad))
        self.driver.setSteeringAngle(-applied)  # Webots positive = right.
        self.driver.setCruisingSpeed(speed_m_s * 3.6)
        return applied

    def state(self):
        position = self.node.getPosition()
        rotation = self.node.getOrientation()  # row-major body-to-world matrix
        velocity = self.node.getVelocity()  # world linear xyz, angular xyz
        heading = math.atan2(rotation[3], rotation[0])  # body +x, ENU CCW
        return {
            't_state_s': self.driver.getTime(),
            'x_m': position[0], 'y_m': position[1], 'z_m': position[2],
            'heading_rad': heading,
            'speed_truth_m_s': velocity[0] * math.cos(heading) + velocity[1] * math.sin(heading),
            'speed_driver_m_s': self.driver.getCurrentSpeed() / 3.6,
            'yaw_rate_rad_s': velocity[5],
            'steering_driver_readback_rad': self.driver.getSteeringAngle(),
            'wheel_left_sensor_rad': self.left.getValue(),
            'wheel_right_sensor_rad': self.right.getValue(),
        }
