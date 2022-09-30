#!/usr/bin/env python3

from absl import logging

import time
from sensirion_i2c_driver import I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_sen5x import Sen5xI2cDevice

from . import Sensor

# Based on https://sensirion.github.io/python-i2c-sen5x/quickstart.html#linux-i2c-bus-example
class Sen5x(Sensor):
  def __init__(self, remotestorage, localstorage, **kwargs):
    super().__init__(remotestorage, localstorage)

    self.i2c_bus = '/dev/i2c-1'
    self.max_wait_sec = 5

    with LinuxI2cTransceiver(self.i2c_bus) as i2c_transceiver:
      device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))

      logging.info("SEN5X Version: {}".format(device.get_version()))
      logging.info("SEN5X Product Name: {}".format(device.get_product_name()))
      logging.info("SEN5X Serial Number: {}".format(device.get_serial_number()))

      # Perform a device reset (reboot firmware)
      device.device_reset()

      # TODO:  Maybe perform fan cleaning sometimes?

  def read(self):
    # TODO:  Are these with blocks actually necessary?  Does this have to be closed?
    # TODO:  Factor the transceiver out into a caller and wrap this, and all other devices, in with blocks passing the needed parameters through to __init__.
    with LinuxI2cTransceiver('/dev/i2c-1') as i2c_transceiver:
      device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))

      # Start measurement
      # TODO:  When we wrap this in a with block, start this at __enter__
      device.start_measurement()

      # Wait until next result is available
      total_wait_sec = 0
      while device.read_data_ready() is False and total_wait_sec < self.max_wait_sec:
        time.sleep(0.1)
        total_wait_sec += 0.1

      if not device.read_data_ready():
        return {}

      # Read measured values -> clears the "data ready" flag
      values = device.read_measured_values()

      # Stop measurement
      # TODO:  When we wrap this in a with block, start this at __exit__
      device.stop_measurement()

    return values

  def publish(self):
    logging.info('Publishing SEN5X to influx')
    result = False
    try:
      data = self.read()

      result = self._try_write_to_remote('SEN5X', 'humidity_percent', data.ambient_humidity.percent_rh) or result
      result = self._try_write_to_remote('SEN5X', 'temperature_C', data.ambient_temperature.degrees_celsius) or result
      result = self._try_write_to_remote('SEN5X', 'pm10.0_ug_m3', data.mass_concentration_10p0.physical) or result
      result = self._try_write_to_remote('SEN5X', 'pm1.0_ug_m3', data.mass_concentration_1p0.physical) or result
      result = self._try_write_to_remote('SEN5X', 'pm2.5_ug_m3', data.mass_concentration_2p5.physical) or result
      result = self._try_write_to_remote('SEN5X', 'pm4.0_ug_m3', data.mass_concentration_4p0.physical) or result
      result = self._try_write_to_remote('SEN5X', 'nox_index', data.nox_index.scaled) or result  # TODO:  This returns nan if not available.  Is that a problem?
      result = self._try_write_to_remote('SEN5X', 'voc_index', data.voc_index.scaled) or result
    except Exception as err:
      logging.error("Error getting data from SEN5X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
