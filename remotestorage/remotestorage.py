from abc import ABC, abstractmethod

class RemoteStorage(ABC):
  """Abstract base class for remote storage backends.

  The current contract between LocalSqlite and RemoteStorage implementations is
  that write() receives a list of JSON-encoded strings (one per cached row).
  Backends that need structured data must deserialize each element themselves.
  Callers may also pass dicts, which backends should accept as-is.
  """

  def __init__(self, endpoint=None, bucket=None, organization=None, token=None):
    self.endpoint = endpoint
    self.bucket = bucket
    self.organization = organization
    self.token = token

  @abstractmethod
  def write(self, data_json):
    pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass
