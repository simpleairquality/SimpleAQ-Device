"""Regression tests for devices/pm25.py."""
import sys
import unittest
from unittest import mock


class TestPm25(unittest.TestCase):

    @mock.patch.dict('sys.modules', {
        'board': mock.MagicMock(),
        'busio': mock.MagicMock(),
        'adafruit_pm25': mock.MagicMock(),
        'adafruit_pm25.i2c': mock.MagicMock(),
    })
    @mock.patch('devices.pm25.PM25_I2C')
    def test_publish_returns_sensor_name_on_read_failure(self, mock_pm25_i2c):
        """If an exception escapes read(), publish() must return self.name.

        The buggy code referenced undefined `device.name`; this test guards
        against that NameError and verifies the intended behavior.
        """
        from devices.pm25 import Pm25

        sensor = Pm25(remotestorage=None, localstorage=None, timesource=None)
        mock_pm25_i2c.return_value.read.side_effect = Exception('read failed')

        result = sensor.publish()

        self.assertEqual(result, 'PM25')
