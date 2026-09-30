"""Tests for the InfluxDB remote-storage backend.

Rows are passed through from LocalSqlite as JSON strings with one of three
shapes:

  {'point': str, 'field': str, 'value': float|int, 'time': str}
  {'point': str, 'field': str, 'message': str, 'time': str}
  {'point': str, 'field': str, 'error': str, 'time': str}

These tests mock the InfluxDB client and assert that each row produces a
single Point written with the correct measurement, field, value, and timestamp.
"""
import json
import unittest
from unittest import mock

from dateutil import parser

from remotestorage.influxstorage import InfluxStorage


def _row(point, field, value=None, message=None, error=None, time='2026-09-30T23:00:00+00:00'):
    data = {'point': point, 'field': field, 'time': time}
    if value is not None:
        data['value'] = value
    if message is not None:
        data['message'] = message
    if error is not None:
        data['error'] = error
    return json.dumps(data)


class TestInfluxStorage(unittest.TestCase):

    def _written_points(self, storage, rows):
        """Call storage.write(rows) and return the points passed to client.write."""
        with storage as s:
            s.influx = mock.Mock()
            s.influx.write_api.return_value.__enter__ = mock.Mock(return_value=mock.Mock())
            captured = []
            def capture(bucket, org, point):
                captured.append((bucket, org, point))
            s.influx.write_api.return_value.__enter__.return_value.write = capture
            s.influx.write_api.return_value.__exit__ = mock.Mock(return_value=False)
            s.write(rows)
        return captured

    def test_value_row_produces_point_with_value_field(self):
        rows = [_row('System', 'uptime_sec', value=123.0)]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 1)
        bucket, org, point = written[0]
        self.assertEqual(bucket, 'test-bucket')
        self.assertEqual(org, 'test-org')
        line = point.to_line_protocol()
        self.assertIn('System', line)
        self.assertIn('uptime_sec=123', line)

    def test_message_row_produces_message_field(self):
        rows = [_row('GPS', 'latitude_degrees', message='No fix')]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 1)
        line = written[0][2].to_line_protocol()
        self.assertIn('latitude_degrees-message="No fix"', line)

    def test_error_row_produces_error_field(self):
        rows = [_row('System', 'simpleaq_build', error='disk full')]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 1)
        line = written[0][2].to_line_protocol()
        self.assertIn('simpleaq_build-error="disk full"', line)
        # Ensure we do not accidentally emit the message payload for error rows.
        self.assertNotIn('message="disk full"', line)

    def test_multi_row_batch_uses_each_rows_values(self):
        rows = [
            _row('System', 'uptime_sec', value=123.0,
                 time='2026-09-30T23:00:00+00:00'),
            _row('SEN5X', 'pm2.5_ug_m3', value=4.5,
                 time='2026-09-30T23:00:01+00:00'),
        ]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 2)
        first = written[0][2].to_line_protocol()
        second = written[1][2].to_line_protocol()
        self.assertIn('System', first)
        self.assertIn('uptime_sec=123', first)
        self.assertIn('SEN5X', second)
        self.assertIn('pm2.5_ug_m3=4.5', second)
        # Timestamps differ by one second.
        self.assertNotEqual(first, second)

    def test_dict_rows_are_accepted_without_deserialization(self):
        rows = [{'point': 'System', 'field': 'uptime_sec', 'value': 42.0,
                 'time': '2026-09-30T23:00:00+00:00'}]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 1)
        line = written[0][2].to_line_protocol()
        self.assertIn('uptime_sec=42', line)

    def test_row_without_required_keys_is_skipped(self):
        rows = [json.dumps({'point': 'System', 'value': 1.0})]

        storage = InfluxStorage(endpoint='http://localhost:8086',
                              bucket='test-bucket',
                              organization='test-org',
                              token='test-token')
        written = self._written_points(storage, rows)

        self.assertEqual(len(written), 0)


if __name__ == '__main__':
    unittest.main()
