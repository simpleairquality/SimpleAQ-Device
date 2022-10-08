import influxdb_client
import requests
from requests_toolbelt import MultipartEncoder

from dateutil import parser
from . import RemoteStorage

class SimpleAQStorage(RemoteStorage): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)

  def write(self, data_json):
    encoder = MultipartEncoder(
        {
            'id': self.bucket,
            'token': self.token,
            'file': ('file', json.dumps(data_json), 'application/ndjson')
        })

    requests.post(
        self.endpoint,
        data=encoder,
        headers={'Content-Type': encoder.content_type}
    )

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass
