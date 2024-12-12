import json
import requests
from requests_toolbelt import MultipartEncoder

from dateutil import parser
from . import RemoteStorage

class SimpleAQStorage(RemoteStorage): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)

  def write(self, data_json):
    # Convert the list of JSON objects to an NDJSON string
    ndjson_data = "\n".join(obj for obj in data_json)

    # Prepare the multipart encoder
    encoder = MultipartEncoder(
        {
            'id': self.bucket,
            'token': self.token,
            'file': ('file', ndjson_data, 'application/ndjson')
        }
    )
  
    # We do not catch requests.exceptions.Timeout here because we expect it will be captured by
    # the caller.
    # TODO:  Configurable request timeout?
    # Send the request
    response = requests.post(
        self.endpoint,
        data=encoder,
        headers={'Content-Type': encoder.content_type},
        timeout=10
    )
    
    if response.status_code >= 400:
      raise Exception(f"Received status {response.status_code} from SimpleAQ endpoint {self.endpoint}")

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass
