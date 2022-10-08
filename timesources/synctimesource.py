import datetime

from . import TimeSource

class SyncTimeSource(TimeSource): 
  def __init__(self):
    self.time = None

  def set_time(self, time):
    self.time = time
    pass

  @abstractmethod
  def get_time(self)
    if self.time is None:
      self.time = datetime.datetime.now()
 
    return self.time.isoformat()
