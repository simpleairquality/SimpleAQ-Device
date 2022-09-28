import influxdb_client

from dateutil import parser
from influxdb_client.client.write_api import SYNCHRONOUS
from . import RemoteStorage

class InfluxStorage(RemoteStorage): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)
    self.influx = None

  def write(self, data_json):
    with self.influx.write_api(write_options=SYNCHRONOUS) as client:
      client.write(
          self.bucket,
          self.organization 
          influxdb_client.Point(data_json.get('point')).field(
               data_json.get('field'), data_json.get('value')).time(parser.parse(data_json.get('time'))))

  def __enter__(self):
    self.influx = influxdb_client.InfluxDBClient(url=self.endpoint, token=self.token, org=self.organization)
    return self

  def __exit__(self, type, value, traceback):
    self.influx.close() 
