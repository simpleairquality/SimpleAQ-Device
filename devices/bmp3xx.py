#!/usr/bin/env python3

from absl import logging
from . import Sensor

import board
import adafruit_bmp3xx


class Bmp3xx(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.sensor = adafruit_bmp3xx.BMP3XX_I2C(board.I2C())
    self.name = "BMP3XX"

  def publish(self):
    logging.info('Publishing BMP3XX Data')
    result = False
    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BMP3XX', 'temperature_C', self.sensor.temperature) or result
    except Exception as err:
      self._try_write_error('BMP3XX', 'temperature_C', str(err))
      logging.error("Error getting data from BMP3XX.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name 

    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BMP3XX', 'pressure_hPa', self.sensor.pressure) or result
    except Exception as err:
      self._try_write_error('BMP3XX', 'pressure_hPa', str(err))
      logging.error("Error getting data from BMP3XX.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name

    return result
