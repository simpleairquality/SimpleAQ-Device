"""Regression tests for devices/system.py."""
import os
import unittest
from unittest import mock


class TestSystem(unittest.TestCase):

    def test_service_uptime_is_less_than_device_uptime(self):
        """service_uptime_sec must be measured from object creation, not boot."""
        from devices.system import System

        with mock.patch('devices.system.psutil') as mock_psutil:
            mock_psutil.boot_time.return_value = 1000.0
            with mock.patch('devices.system.time') as mock_time:
                # First call is start_time; remaining calls are inside publish().
                mock_time.time.side_effect = [1500.0, 1600.0, 1600.0, 1600.0, 1600.0]
                with mock.patch.object(System, '_try_write') as mock_try_write:
                    sensor = System(remotestorage=None, localstorage=None, timesource=None)
                    os.environ['image_name'] = 'test-image-123'
                    sensor.publish()

        calls = {call.args[1]: call.args[2] for call in mock_try_write.call_args_list}
        self.assertEqual(calls['device_uptime_sec'], 600.0)
        self.assertEqual(calls['service_uptime_sec'], 100.0)

    def test_image_name_read_from_environment(self):
        """Reading image_name must not raise NameError due to missing os import."""
        from devices.system import System

        with mock.patch('devices.system.psutil') as mock_psutil:
            mock_psutil.boot_time.return_value = 1000.0
            with mock.patch('devices.system.time') as mock_time:
                mock_time.time.return_value = 1600.0
                with mock.patch.object(System, '_try_write') as mock_try_write:
                    sensor = System(remotestorage=None, localstorage=None, timesource=None)
                    os.environ['image_name'] = 'test-image-456'
                    sensor.publish()

        calls = {call.args[1]: call.args[2] for call in mock_try_write.call_args_list}
        self.assertEqual(calls['simpleaq_build'], 'test-image-456')


if __name__ == '__main__':
    unittest.main()
