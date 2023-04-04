#!/usr/bin/env python3

from absl import logging
from . import Sensor

import board
import adafruit_bmp3xx


class Bmp3xx(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.sensor = adafruit_bmp3xx.BMP3XX_I2C(board.I2C())

  def publish(self):
    logging.info('Publishing Bmp3xx to remote')
    result = False
    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write_to_remote('BMP3XX', 'temperature_C', self.sensor.temperature) or result
      result = self._try_write_to_remote('BMP3XX', 'pressure_hPa', self.sensor.pressure) or result
    except Exception as err:
      logging.error("Error getting data from BMP3XX.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True
    return result
