#!/usr/bin/env python3

from absl import logging
from . import Sensor

import board
import adafruit_bmp3xx
import time
from adafruit_bmp3xx import _REGISTER_CONTROL, _REGISTER_STATUS, _REGISTER_PRESSUREDATA
from types import MethodType


def patch_bmp3xx_read(self):
  """Returns a tuple for temperature and pressure."""
  # OK, pylint. This one is all kinds of stuff you shouldn't worry about.
  # pylint: disable=invalid-name, too-many-locals

  # Perform one measurement in forced mode
  self._write_register_byte(_REGISTER_CONTROL, 0x13)

  # Wait for *both* conversions to complete
  max_wait_time = 5
  wait_time = 0
  while self._read_byte(_REGISTER_STATUS) & 0x60 != 0x60 and wait_time < max_wait_time:
    wait_time += self._wait_time
    time.sleep(self._wait_time)

  logging.info("Waited for {}s".format(wait_time))
  if wait_time >= max_wait_time:
    logging.info("Timed out waiting for data in BMP3XX")
    raise Exception("Timed out waiting for data in BMP3XX")

  # Get ADC values
  data = self._read_register(_REGISTER_PRESSUREDATA, 6)
  adc_p = data[2] << 16 | data[1] << 8 | data[0]
  adc_t = data[5] << 16 | data[4] << 8 | data[3]

  # datasheet, sec 9.2 Temperature compensation
  T1, T2, T3 = self._temp_calib

  pd1 = adc_t - T1
  pd2 = pd1 * T2

  temperature = pd2 + (pd1 * pd1) * T3

  # datasheet, sec 9.3 Pressure compensation
  P1, P2, P3, P4, P5, P6, P7, P8, P9, P10, P11 = self._pressure_calib

  pd1 = P6 * temperature
  pd2 = P7 * temperature**2.0
  pd3 = P8 * temperature**3.0
  po1 = P5 + pd1 + pd2 + pd3

  pd1 = P2 * temperature
  pd2 = P3 * temperature**2.0
  pd3 = P4 * temperature**3.0
  po2 = adc_p * (P1 + pd1 + pd2 + pd3)

  pd1 = adc_p**2.0
  pd2 = P9 + P10 * temperature
  pd3 = pd1 * pd2
  pd4 = pd3 + P11 * adc_p**3.0

  pressure = po1 + po2 + pd4

  # pressure in hPa, temperature in deg C
  return pressure, temperature


class Bmp3xx(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.sensor = adafruit_bmp3xx.BMP3XX_I2C(board.I2C())

    # We encounter an issue where bus instability causes an infinite loop in default
    # adafruit_bmp3xx read.
    self.sensor._read = MethodType(patch_bmp3xx_read, self.sensor)
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
