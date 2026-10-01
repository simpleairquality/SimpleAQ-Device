"""Regression test for the main loop interval timing fix."""
import sys
import types
import unittest
from unittest import mock


class TestSimpleaqTiming(unittest.TestCase):

    def test_sleep_computes_target_time_to_avoid_drift(self):
        """The main loop must sleep until the next target time, not just interval seconds.

        This is a structural test: it verifies that the code computes sleep_for
        from a target time and passes it to time.sleep, rather than calling
        time.sleep(interval). The actual trivial unit test for average interval
        is impossible without a larger refactor, so this test guards against
        reverting to the old drift-prone pattern.
        """
        # Make simpleaq importable by stubbing heavy deps.
        for name in ['devices', 'localstorage', 'remotestorage', 'timesources']:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            sys.modules[name] = pkg

        submods = [
            'devices.system', 'devices.bme688', 'devices.bmp3xx', 'devices.gps',
            'devices.pm25', 'devices.sen5x', 'devices.sen6x',
            'devices.dfrobot_multigassensor', 'devices.pcbartists_decibel',
            'devices.uartnmeagps', 'devices.scd4x', 'devices.lps28',
            'localstorage.localdummy', 'localstorage.localsqlite',
            'remotestorage.dummystorage', 'remotestorage.influxstorage',
            'remotestorage.simpleaqstorage',
            'timesources.systemtimesource', 'timesources.synctimesource',
        ]
        for mod in submods:
            sys.modules[mod] = mock.MagicMock()

        sys.modules['RPi'] = mock.MagicMock()
        sys.modules['RPi.GPIO'] = mock.MagicMock()
        sys.modules['sensirion_i2c_driver'] = mock.MagicMock()

        import importlib
        import simpleaq
        importlib.reload(simpleaq)

        source = open('SimpleAQ-Device/simpleaq.py').read()
        # The old buggy code called time.sleep(interval).
        self.assertNotIn('time.sleep(interval)', source)
        # The fixed code computes a sleep_for target.
        self.assertIn('sleep_for = max(0.0, next_time - time.time())', source)
        self.assertIn('time.sleep(sleep_for)', source)
