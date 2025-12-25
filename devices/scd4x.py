#!/usr/bin/env python3

from absl import logging
from . import Sensor

import board
import adafruit_scd4x

class Scd4x(Sensor):
  I2C_ADDRESS = 0x62

  def __init__(self, remotestorage, localstorage, timesource, i2c_transceiver, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.sensor = adafruit_scd4x.SCD4X(board.I2C())
    self.name = "SCD4X"
    self.i2c_transceiver = i2c_transceiver
    self.has_reported_serial = False

    if not self._probe_device:
      raise Exception("No device at SCD4X's I2C address, 0x62")

    self.serial_number = "".join(f"{word:04X}" for word in self.sensor.serial_number)
    self.sensor.start_periodic_measurement()

  def _probe_device(self):
    """Attempt to detect device presence with minimal bus interaction"""
    try:
      # Try a zero-byte write - many I2C implementations support this for device detection
      status, error, _ = self.i2c_transceiver.transceive(
          self.I2C_ADDRESS,
          bytes([]),  # Empty write
          0,  # No read
          read_delay=0,
          timeout=1  # Short timeout for probe
      )
      return status and not error
    except:
      return False

  def publish(self):
    logging.info('Publishing SCD4X Data')
    result = False

    if self.sensor.data_ready:
      if not self.has_reported_serial:
        try:
          # It is actually important that the try_write_to_remote happens before the result, otherwise
          # it will never be evaluated!
          result = self._try_write('SCD4X', 'serial_number', self.serial_number) or result
          self.has_reported_serial = True
        except Exception as err:
          self._try_write_error('SCD4X', 'serial_number', str(err))
          logging.error("Error getting data from SCD4X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
          result = self.name

      try:
        # It is actually important that the try_write_to_remote happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write('SCD4X', 'temperature_C', self.sensor.temperature) or result
      except Exception as err:
        self._try_write_error('SCD4X', 'temperature_C', str(err))
        logging.error("Error getting data from SCD4X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
        result = self.name 

      try:
        # It is actually important that the try_write_to_remote happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write('SCD4X', 'co2_ppm', self.sensor.CO2) or result
      except Exception as err:
        self._try_write_error('SCD4X', 'co2_ppm', str(err))
        logging.error("Error getting data from SCD4X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
        result = self.name 

      try:
        # It is actually important that the try_write_to_remote happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write('SCD4X', 'relative_humidity_pct', self.sensor.relative_humidity) or result
      except Exception as err:
        self._try_write_error('SCD4X', 'relative_humidity_pct', str(err))
        logging.error("Error getting data from SCD4X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
        result = self.name 

    return result
