"""Regression tests for devices/lps28.py."""
import sys
import unittest
from unittest import mock


class TestLps28(unittest.TestCase):

    def test_init_raises_when_probe_returns_false(self):
        """If the I2C probe finds no device, __init__ must raise an exception.

        The buggy code treated the method object itself as truthy, so it never
        detected a missing device.
        """
        with mock.patch.dict('sys.modules', {
            'board': mock.MagicMock(),
            'adafruit_lps28': mock.MagicMock(),
        }):
            from devices.lps28 import Lps28

            mock_transceiver = mock.MagicMock()
            mock_transceiver.transceive.return_value = (False, None, None)

            with self.assertRaises(Exception) as ctx:
                Lps28(remotestorage=None,
                      localstorage=None,
                      timesource=None,
                      i2c_transceiver=mock_transceiver)

        self.assertIn('0x5C', str(ctx.exception))
