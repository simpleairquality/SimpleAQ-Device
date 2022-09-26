#!/usr/bin/env python3

import contextlib
import datetime
import json
import os

from absl import logging

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS


class Sensor(object):
  def __init__(self, influx, connection):
    self.influx = influx
    self.connection = connection
    self.bucket = os.getenv('influx_bucket')
    self.org = os.getenv('influx_org')

  # Even though we never explicitly create rows, InfluxDB assigns a type
  # when a row is first written.  Apparently, sometimes intended float values are incorrectly
  # interpreted as a int and changing field types after the fact is hard.
  # So let's avoid that hassle entirely.
  def _make_ints_to_float(self, value):
    if isinstance(value, int):
      return float(value)
    return value

  def _try_write_to_influx(self, point, field, value):
    try:
      with self.influx.write_api(write_options=SYNCHRONOUS) as client:
        client.write(
            self.bucket,
            self.org,
            influxdb_client.Point(point).field(
                field, self._make_ints_to_float(value)).time(datetime.datetime.now()))
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
            'time': datetime.datetime.now().isoformat()
        }

        with contextlib.closing(self.connection.cursor()) as cursor:
          cursor.execute("INSERT INTO data (json) VALUES(?)", (json.dumps(data_json),))
          self.connection.commit()

        return True
      except Exception as backup_err:
        # Something has truly gone sideways.  We can't even write backup data.
        logging.error("Error saving data to local disk: " + str(backup_err))
        return True
