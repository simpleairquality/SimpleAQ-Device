"""Regression tests for simpleaq.py subprocess and timing behavior."""
import ast
import sys
import types
import unittest
from unittest import mock


class TestSimpleaqDiagnostics(unittest.TestCase):

    def _import_simpleaq_helpers(self):
        """Mock heavy/incompatible imports so simpleaq loads for testing helpers."""
        # Make 'devices' and 'localstorage'/'remotestorage'/'timesources' packages
        # so simpleaq's submodule imports succeed.
        for name in ['devices', 'localstorage', 'remotestorage', 'timesources']:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            sys.modules[name] = pkg

        # Mock submodules used by simpleaq.
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
        return simpleaq

    def test_collect_diagnostic_logs_uses_list_args_no_shell(self):
        """Diagnostic collection must run commands as list args, not shell strings."""
        simpleaq = self._import_simpleaq_helpers()

        with mock.patch('simpleaq.subprocess.run') as mock_run:
            mock_run.return_value = mock.MagicMock(stdout="line1\nline2\n")
            simpleaq._collect_diagnostic_logs()

        commands = [call.args[0] for call in mock_run.call_args_list]
        for cmd in commands:
            self.assertIsInstance(cmd, list)
            joined = ' '.join(cmd)
            self.assertNotIn('|', joined)
            self.assertNotIn('&&', joined)
            self.assertNotIn('||', joined)

        self.assertIn(['dmesg'], commands)
        self.assertIn(['journalctl', '-u', 'simpleaq.service'], commands)
        self.assertIn(['journalctl', '-u', 'NetworkManager'], commands)

    def test_tail_lines_returns_last_n_lines(self):
        """_tail_lines must return only the last n lines joined by newlines."""
        simpleaq = self._import_simpleaq_helpers()

        text = "\n".join("line{}".format(i) for i in range(150))
        result = simpleaq._tail_lines(text, 100)
        lines = result.splitlines()
        self.assertEqual(len(lines), 100)
        self.assertEqual(lines[0], "line50")
        self.assertEqual(lines[-1], "line149")

    def test_no_os_system_or_shell_true_after_cleanup(self):
        """simpleaq.py must no longer use os.system or subprocess.run(shell=True)."""
        path = 'SimpleAQ-Device/simpleaq.py'
        with open(path, encoding='utf-8') as f:
            tree = ast.parse(f.read())

        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    if func.attr == 'run':
                        for kw in node.keywords:
                            if kw.arg == 'shell' and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                offenders.append(('subprocess.run(shell=True)', node.lineno))
                    if func.attr == 'system':
                        offenders.append(('os.system call', node.lineno))

        self.assertEqual(offenders, [], "Found shell=True or os.system calls: {}".format(offenders))
