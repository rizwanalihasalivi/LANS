"""Boundary tests complement, but do not replace, the Webots physics runs."""
import math
import unittest
from adapter import VehicleAdapter


class Sensor:
    def enable(self, period):
        self.period = period


class DriverStub:
    def getSelf(self):
        return self

    def getBasicTimeStep(self):
        return 10

    def getDevice(self, name):
        return Sensor()

    def setSteeringAngle(self, value):
        self.angle = value

    def setCruisingSpeed(self, value):
        self.speed = value


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.driver = DriverStub()
        self.adapter = VehicleAdapter(self.driver)

    def test_full_command_sign_and_speed_units(self):
        self.assertEqual(self.adapter.command(0.03, 5), 0.03)
        self.assertEqual(self.driver.angle, -0.03)
        self.assertEqual(self.driver.speed, 18)
        self.adapter.command(-0.03, 5)
        self.assertEqual(self.driver.angle, 0.03)

    def test_saturation_both_directions(self):
        for requested, expected in ((2, .5), (-2, -.5)):
            self.assertEqual(self.adapter.command(requested, 0), expected)
            self.assertEqual(self.driver.angle, -expected)

    def test_invalid_commands_are_rejected_before_driver_calls(self):
        for steering, speed in ((math.nan, 5), (math.inf, 5), (0, math.nan), (0, math.inf), (0, -1)):
            with self.subTest(steering=steering, speed=speed):
                with self.assertRaises(ValueError):
                    self.adapter.command(steering, speed)
                self.assertFalse(hasattr(self.driver, 'angle'))

    def test_invalid_limits(self):
        for limit in (0, -.1, .6, math.nan):
            with self.assertRaises(ValueError):
                VehicleAdapter(self.driver, limit)


if __name__ == '__main__':
    unittest.main()
