#!/usr/bin/env python3

import datetime
import os

from absl import logging


class Sensor(object):
  def __init__(self, remotestorage, localstorage, **kwargs):
    self.remotestorage = remotestorage
    self.localstorage = localstorage

  # Even though we never explicitly create rows, InfluxDB assigns a type
  # when a row is first written.  Apparently, sometimes intended float values are incorrectly
  # interpreted as a int and changing field types after the fact is hard.
  # So let's avoid that hassle entirely.
  def _make_ints_to_float(self, value):
    if isinstance(value, int):
      return float(value)
    return value

  def _try_write_to_remote(self, point, field, value):
    try:
      self.remotestorage.write({'point': point, 'field': field, 'value': self._make_ints_to_float(value), 'time': datetime.datetime.now().isoformat()})
      return False
    except Exception as err:
      logging.error("Could not write to InfluxDB: " + str(err))

      # If we failed to write, save to disk instead.
      # Need to make sure the path exists first.
      try:
        data_json = {
            'point': point,
            'field': field,
            'value': self._make_ints_to_float(value),
            'time': datetime.datetime.now().astimezone().isoformat()
        }

        self.localstorage.writejson(data_json);

        return True
      except Exception as backup_err:
        # Something has truly gone sideways.  We can't even write backup data.
        logging.error("Error saving data to local disk: " + str(backup_err))
        return True

  def __enter__(self):
    pass

  def __exit__(self):
    pass
