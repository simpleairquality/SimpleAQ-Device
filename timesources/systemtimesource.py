import datetime

from . import TimeSource

class SystemTimeSource(TimeSource): 
  def __init__(self):
    pass

  def set_time(self, time):
    pass

  @abstractmethod
  def get_time(self):
    return datetime.datetime.now().isoformat()
