import contextlib
import json
import os
import sqlite3

from . import LocalStorage 


class LocalSqlite(LocalStorage): 
  def __init__(self, db_path):
    super(LocalStorage, self).__init__()
    self.db_path = db_path
    self.db_conn = None

  def countrecords(self):
    with contextlib.closing(self.db_conn.cursor()) as cursor:
      result = cursor.execute("SELECT COUNT(*) FROM data")
      return result.fetchone()[0]

  def deleterecord(self, record_id):
    with contextlib.closing(self.db_conn.cursor()) as delete_cursor:
      delete_cursor.execute("DELETE FROM data WHERE id=?", (record_id,))
      self.db_conn.commit()

  def deleteall(self):
    with contextlib.closing(self.db_conn.cursor()) as cursor:
      cursor.execute("DELETE FROM data")
      self.db_conn.commit()

  # This cursor returns all and MUST be closed by the caller.
  def getcursor(self):
    cursor = self.db_conn.cursor()
    cursor.execute("SELECT * FROM data")

    return cursor

  def writejson(self, json_message):
    with contextlib.closing(self.db_conn.cursor()) as cursor:
      cursor.execute("INSERT INTO data (json) VALUES(?)", (json.dumps(json_message),))
      self.db_conn.commit()

  def __enter__(self):
    # There needs to actually be a place to put the data.
    os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    # Create a connection.  This will be closed later in __exit__.
    self.db_conn = sqlite3.connect(self.db_path)

    # Maybe create the table.
    with contextlib.closing(self.db_conn.cursor()) as cursor:
      cursor.execute("CREATE TABLE IF NOT EXISTS data(id INTEGER PRIMARY KEY AUTOINCREMENT, json TEXT)")
      self.db_conn.commit()

    return self

  def __exit__(self, type, value, traceback):
    if self.db_conn:
      self.db_conn.close()
