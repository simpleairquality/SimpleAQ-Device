#!/usr/bin/env python3

from absl import logging

import board
import busio
from adafruit_pm25.i2c import PM25_I2C

from . import Sensor


class Pm25(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    self.pm25 = PM25_I2C(i2c)

  def read(self):
    try:
      aqdata = self.pm25.read()
    except RuntimeError as e:
      logging.error(f"Couldn't read data from PM2.5 sensor: {e}")
      return {}
    return aqdata

  def publish(self):
    logging.info('Publishing PM2.5 to remote')
    result = False
    try:
      aqdata = self.read()

      for key, val in aqdata.items():
        remote_key = key
        if remote_key.startswith('particles'):
          remote_key += " per dL"
        if remote_key.endswith('env'):
          remote_key += " ug per m3"
        if remote_key.endswith('standard'):
          remote_key += " ug per m3"
        # It is actually important that the try_write_to_remote happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write_to_remote('PM25', remote_key, val) or result
    except Exception as err:
      logging.error("Error getting data from PM25.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
