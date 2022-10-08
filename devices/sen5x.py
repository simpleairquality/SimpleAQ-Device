#!/usr/bin/env python3

from absl import logging

import time
from sensirion_i2c_driver import I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_sen5x import Sen5xI2cDevice

from . import Sensor

# Based on https://sensirion.github.io/python-i2c-sen5x/quickstart.html#linux-i2c-bus-example
class Sen5x(Sensor):
  def __init__(self, remotestorage, localstorage, i2c_transceiver, **kwargs):
    super().__init__(remotestorage, localstorage)

    self.i2c_transceiver = i2c_transceiver
    self.device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))

    logging.info("SEN5X Version: {}".format(self.device.get_version()))
    self._try_write_to_remote('SEN5X', 'firmware_version', '{}.{}'.format(self.device.get_version().firmware.major, self.device.get_version().firmware.minor))
    self._try_write_to_remote('SEN5X', 'hardware_version', '{}.{}'.format(self.device.get_version().hardware.major, self.device.get_version().hardware.minor))
    self._try_write_to_remote('SEN5X', 'protocol_version', '{}.{}'.format(self.device.get_version().protocol.major, self.device.get_version().protocol.minor))
    logging.info("SEN5X Product Name: {}".format(self.device.get_product_name()))
    self._try_write_to_remote('SEN5X', 'product_name', self.device.get_product_name())
    logging.info("SEN5X Serial Number: {}".format(self.device.get_serial_number()))
    self._try_write_to_remote('SEN5X', 'serial_number', self.device.get_serial_number())
 
    # Perform a device reset (reboot firmware)
    self.device.device_reset()

  def read(self):
    if not self.device.read_data_ready():
      return None 

    # Read measured values -> clears the "data ready" flag
    values = self.device.read_measured_values()

    return values

  def publish(self):
    logging.info('Publishing SEN5X to influx')
    result = False
    try:
      data = self.read()

      if data:
        result = self._try_write_to_remote('SEN5X', 'humidity_percent', data.ambient_humidity.percent_rh) or result
        result = self._try_write_to_remote('SEN5X', 'temperature_C', data.ambient_temperature.degrees_celsius) or result
        result = self._try_write_to_remote('SEN5X', 'pm10.0_ug_m3', data.mass_concentration_10p0.physical) or result
        result = self._try_write_to_remote('SEN5X', 'pm1.0_ug_m3', data.mass_concentration_1p0.physical) or result
        result = self._try_write_to_remote('SEN5X', 'pm2.5_ug_m3', data.mass_concentration_2p5.physical) or result
        result = self._try_write_to_remote('SEN5X', 'pm4.0_ug_m3', data.mass_concentration_4p0.physical) or result
        result = self._try_write_to_remote('SEN5X', 'nox_index', data.nox_index.scaled) or result  # TODO:  This returns nan if not available.  Is that a problem?
        result = self._try_write_to_remote('SEN5X', 'voc_index', data.voc_index.scaled) or result
      else:
        logging.info("Data was not ready for SEN5X.")
    except Exception as err:
      logging.error("Error getting data from SEN5X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result

  def __enter__(self):
    self.device.start_measurement()

  def __exit__(self):
    self.device.stop_measurement()
