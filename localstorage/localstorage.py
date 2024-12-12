from abc import ABC, abstractmethod

class LocalStorage(ABC): 
  def __init__(self):
    pass

  @abstractmethod
  def countrecords(self):
    pass

  @abstractmethod
  def deleterecord(self, record_id):
    pass

  @abstractmethod
  def getcursor(self):
    pass

  @abstractmethod
  def getrecent(self, num):
    pass

  @abstractmethod
  def deleteall(self):
    pass

  @abstractmethod
  def writejson(self, json_message):
    pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass
