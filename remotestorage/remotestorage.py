from abc import ABC, abstractmethod

class RemoteStorage(ABC): 
  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    self.endpoint = endpoint
    self.bucket = bucket
    self.organization = organization
    self.token = token

  @abstractmethod
  def write(self):
    pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass
