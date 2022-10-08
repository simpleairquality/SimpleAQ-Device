#!/usr/bin/env python3

import contextlib
import os

from absl import app, flags, logging
from localstorage.localdummy import LocalDummy
from remotestorage.dummystorage import DummyStorage
from sensirion_i2c_driver import LinuxI2cTransceiver

import dotenv

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

from devices.system import System
from devices.bme688 import Bme688
from devices.gps import Gps
from devices.pm25 import Pm25
from devices.sen5x import Sen5x


FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


device_map = {
    'system': System,
    'bme688': Bme688,
    'gps': Gps,
    'pm25': Pm25,
    'sen5x': Sen5x
}

def main(args):
  with contextlib.closing(LocalDummy()) as local_storage:
    with DummyStorage() as remote_storage:
      with LinuxI2cTransceiver(os.getenv('i2c_bus')) as i2c_transceiver:
        interval = int(os.getenv('simpleaq_interval', 60))

        for name, device in device_map.items():
          try:
            device(remotestorage=remote_storage, localstorage=local_storage, i2c_transceiver=i2c_transceiver).publish()
            logging.info("Detected device: {}".format(name))
          except Exception as err:
            logging.error(str(err))
            logging.info("Device not detected: {}".format(name))


if __name__ == '__main__':
  app.run(main)
