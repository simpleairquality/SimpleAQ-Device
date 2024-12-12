#!/usr/bin/env python3

from absl import logging
from . import Sensor

import board
import adafruit_bme680


class Bme688(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.sensor = adafruit_bme680.Adafruit_BME680_I2C(board.I2C())
    self.name = "BME688"

  def publish(self):
    logging.info('Publishing BME688 Data')
    result = False
    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BME688', 'temperature_C', self.sensor.temperature) or result
    except Exception as err:
      self._try_write_error('BME688', 'temperature_C', str(err))
      logging.error("Error getting data from BME688.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name 

    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BME688', 'voc_ohms', self.sensor.gas) or result
    except Exception as err:
      self._try_write_error('BME688', 'voc_ohms', str(err))
      logging.error("Error getting data from BME688.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name 

    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BME688', 'relative_humidity_pct', self.sensor.humidity) or result
    except Exception as err:
      self._try_write_error('BME688', 'relative_humidity_pct', str(err))
      logging.error("Error getting data from BME688.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name 

    try:
      # It is actually important that the try_write_to_remote happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write('BME688', 'pressure_hPa', self.sensor.pressure) or result
    except Exception as err:
      self._try_write_error('BME688', 'pressure_hPa', str(err))
      logging.error("Error getting data from BME688.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name

    return result
