import json

import influxdb_client

from dateutil import parser
from influxdb_client.client.write_api import SYNCHRONOUS
from . import RemoteStorage

class InfluxStorage(RemoteStorage):
  """Writes cached sensor rows to an InfluxDB bucket.

  Rows are passed through from LocalSqlite, where each row is a JSON string
  with one of the following shapes:

    {'point': <str>, 'field': <str>, 'value': <float|int>, 'time': <str>}
    {'point': <str>, 'field': <str>, 'message': <str>, 'time': <str>}
    {'point': <str>, 'field': <str>, 'error': <str>, 'time': <str>}

  To preserve the string-row contract shared with SimpleAQStorage, this backend
  deserializes strings internally; dicts are accepted as-is for tests or future
  callers. Each row produces a single InfluxDB Point.
  """

  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)
    self.influx = None

  def write(self, data_json):
    with self.influx.write_api(write_options=SYNCHRONOUS) as client:
      for row_or_str in data_json:
        if isinstance(row_or_str, str):
          row = json.loads(row_or_str)
        else:
          row = row_or_str

        if not (row.get('point') and row.get('field') and row.get('time')):
          continue

        point = influxdb_client.Point(row['point']).time(
            parser.parse(row['time']))

        if 'value' in row:
          point = point.field(row['field'], row['value'])
        if 'message' in row:
          point = point.field(row['field'] + '-message', row['message'])
        if 'error' in row:
          point = point.field(row['field'] + '-error', row['error'])

        client.write(self.bucket, self.organization, point)

  def __enter__(self):
    self.influx = influxdb_client.InfluxDBClient(url=self.endpoint, token=self.token, org=self.organization)
    return self

  def __exit__(self, type, value, traceback):
    self.influx.close()
