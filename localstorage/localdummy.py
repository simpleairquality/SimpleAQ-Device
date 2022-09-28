from . import LocalStorage

class LocalDummy(LocalStorage): 
  def __init__(self):
    super().__init__()

  def countrecords(self):
    return 0 

  def deleterecord(self, record_id):
    pass

  def getcursor(self):
    raise NotImplementedError("No cursor can be returned because the storage dummy is not a databaase.")

  def deleteall(self):
    pass

  def writejson(self, json_message):
    pass

  def close(self):
    pass

  def __enter__(self):
    return self

  def __exit__(self, type, value, traceback):
    pass

  

