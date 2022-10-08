from . import RemoteStorage

class DummyStorage(RemoteStorage): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    super().__init__(endpoint=endpoint, bucket=bucket, organization=organization, token=token)

  def write(self, data_json):
    pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass 
