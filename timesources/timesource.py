from abc import ABC, abstractmethod

class TimeSource(ABC): 
  def __init__(self):
    pass

  @abstractmethod
  def set_time(self, time):
    pass

  @abstractmethod
  def get_time(self):
    pass
