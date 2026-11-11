/* Identical1ms Driver/sensor calls; no integration or sensing steps are skipped. */
#include <math.h>
#include <webots/vehicle/driver.h>
#include <webots/position_sensor.h>

int lans_physical_steps(int count, double dt, double target, double cruise,
                        double actuator, double previous, WbDeviceTag left,
                        WbDeviceTag right, double *out) {
  if (count <= 0 || dt != .001 || !isfinite(target) || !isfinite(cruise) ||
      !isfinite(actuator) || !isfinite(previous)) return -2;
  double max_actuator = 0., max_measured = 0.;
  for (int i = 0; i < count; ++i) {
    double old = actuator, lo = actuator - .59 * dt, hi = actuator + .59 * dt;
    actuator = target < lo ? lo : target > hi ? hi : target;
    double rate = fabs(actuator - old) / dt;
    if (rate > max_actuator) max_actuator = rate;
    wbu_driver_set_steering_angle(-actuator);
    wbu_driver_set_cruising_speed(cruise * 3.6);
    if (wbu_driver_step() == -1) return -1;
    double measured = -(wb_position_sensor_get_value(left) + wb_position_sensor_get_value(right)) / 2.;
    if (!isfinite(measured)) return -3;
    rate = fabs(measured - previous) / dt;
    if (rate > max_measured) max_measured = rate;
    previous = measured;
  }
  out[0] = actuator; out[1] = previous;
  out[2] = max_actuator; out[3] = max_measured;
  return count;
}
