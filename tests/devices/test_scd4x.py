"""Regression tests for devices/scd4x.py."""
import sys
import unittest
from unittest import mock


class TestScd4x(unittest.TestCase):

    def test_init_raises_when_probe_returns_false(self):
        """If the I2C probe finds no device, __init__ must raise an exception.

        The buggy code treated the method object itself as truthy, so it never
        detected a missing device.
        """
        with mock.patch.dict('sys.modules', {
            'board': mock.MagicMock(),
            'adafruit_scd4x': mock.MagicMock(),
        }):
            from devices.scd4x import Scd4x

            mock_transceiver = mock.MagicMock()
            mock_transceiver.transceive.return_value = (False, None, None)

            with self.assertRaises(Exception) as ctx:
                Scd4x(remotestorage=None,
                      localstorage=None,
                      timesource=None,
                      i2c_transceiver=mock_transceiver)

        self.assertIn('0x62', str(ctx.exception))
