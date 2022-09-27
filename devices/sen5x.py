#!/usr/bin/env python3

from absl import logging

import time
from sensirion_i2c_driver import I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_sen5x import Sen5xI2cDevice

from . import Sensor

# Based on https://sensirion.github.io/python-i2c-sen5x/quickstart.html#linux-i2c-bus-example
class Sen5x(Sensor):
  def __init__(self, influx, connection):
    super().__init__(influx, connection)

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
    with LinuxI2cTransceiver('/dev/i2c-1') as i2c_transceiver:
      device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))

      # Start measurement
      device.start_measurement()

      # Wait until next result is available
      total_wait_sec = 0
      while device.read_data_ready() is False and total_wait_time < self.max_wait_sec:
        time.sleep(0.1)
        total_wait_sec += 0.1

      if not device.read_data_ready():
        return {}

      # Read measured values -> clears the "data ready" flag
      values = device.read_measured_values()

      # TODO:  Remove this pending debugging.  I don't actually know what's in here.
      print(values)

    # Stop measurement
    device.stop_measurement()

    return values

  def publish(self):
    logging.info('Publishing SEN5X to influx')
    result = False
    try:
      data = self.read()

      for key, val in data.items():
        result = self._try_write_to_influx('SEN5X', key, val) or result
    except Exception as err:
      logging.error("Error getting data from SEN5X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
