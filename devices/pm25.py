#!/usr/bin/env python3

from absl import logging

import board
import busio
from adafruit_pm25.i2c import PM25_I2C

from . import Sensor


class Pm25(Sensor):
  def __init__(self, influx, connection):
    super().__init__(influx, connection)
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
    logging.info('Publishing PM2.5 to influx')
    result = False
    try:
      aqdata = self.read()

      for key, val in aqdata.items():
        influx_key = key
        if influx_key.startswith('particles'):
          influx_key += " per dL"
        if influx_key.endswith('env'):
          influx_key += " ug per m3"
        if influx_key.endswith('standard'):
          influx_key += " ug per m3"
        # It is actually important that the try_write_to_influx happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write_to_influx('PM25', influx_key, val) or result
    except Exception as err:
      logging.error("Error getting data from PM25.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
