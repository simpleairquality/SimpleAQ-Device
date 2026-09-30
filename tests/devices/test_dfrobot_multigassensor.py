"""Regression tests for devices/dfrobot_multigassensor.py."""
import sys
import unittest
from unittest import mock


class TestDFRobotMultiGas(unittest.TestCase):

    @mock.patch.dict('sys.modules', {
        'spidev': mock.MagicMock(),
        'RPi': mock.MagicMock(),
        'RPi.GPIO': mock.MagicMock(),
        'sensirion_i2c_driver': mock.MagicMock(),
        'sensirion_i2c_driver.i2c_connection': mock.MagicMock(),
    })
    @mock.patch('devices.dfrobot_multigassensor.DFRobot_MultiGasSensor_I2C')
    @mock.patch('devices.dfrobot_multigassensor.logging')
    def test_temperature_failure_uses_logging_error(self, mock_logging, mock_sensor_i2c):
        """When temperature write fails, the code must use logging.error.

        The buggy code called logging.err, which does not exist and would raise
        AttributeError.
        """
        from devices.dfrobot_multigassensor import DFRobotMultiGas00

        # Make the constructor's change_acquire_mode loop succeed.
        mock_sensor_i2c.return_value.change_acquire_mode.return_value = True
        mock_sensor_i2c.return_value.gastype = 'CO'
        mock_sensor_i2c.return_value.gasunits = 'ppm'
        mock_sensor_i2c.return_value.temp = 25.0

        sensor = DFRobotMultiGas00(
            remotestorage=None,
            localstorage=None,
            timesource=None,
            i2c_transceiver=mock.MagicMock())

        # Force the temperature _try_write to raise.
        with mock.patch.object(sensor, '_try_write') as mock_try_write:
            mock_try_write.side_effect = RuntimeError('write failed')
            result = sensor.publish()
            self.assertEqual(result, 'DFRobotMultiGas00')

        # logging.err is the bug; logging.error is correct.
        mock_logging.error.assert_called_once()
        self.assertFalse(hasattr(mock_logging, 'err') and mock_logging.err.called)
