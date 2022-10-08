import influxdb_client
import requests
from requests_toolbelt import MultipartEncoder

from dateutil import parser
from . import RemoteStorage

class SimpleAQStorage(RemoteStorage): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)
    self.token = token
    self.endpoint = endpoint

  def write(self, data_json):
    encoder = MultipartEncoder(
        {
            'id': args.bucket,
            'token': args.token,
            'file': ('file', json.dumps(data_json), 'application/ndjson')
        })

    requests.post(
        self.endpoint,
        data=encoder,
        headers={'Content-Type': encoder.content_type}
    )

  def __enter__(self):
    pass

  def __exit__(self, type, value, traceback):
    pass
