#!/usr/bin/env python3

import contextlib
import os

from absl import app, flags, logging
from localstorage.localdummy import LocalDummy
from remotestorage.dummystorage import DummyStorage

import dotenv

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


def main(args):
  with contextlib.closing(LocalDummy()) as local_storage:
    with DummyStorage() as remote_storage:
      interval = int(os.getenv('simpleaq_interval', 60))

      try:
        from devices.system import System
        System(remote_storage, local_storage).publish()
        print("FOUND System")
      except Exception:
        print("NOT FOUND System")

      try:
        from devices.bme688 import Bme688
        Bme688(remote_storage, local_storage).publish()
        print("FOUND Bme688")
      except Exception:
        print("NOT FOUND Bme688")

      try:
        from devices.gps import Gps
        Gps(remote_storage, local_storage).publish()
        print("FOUND Gps")
      except Exception:
        print("NOT FOUND Gps")

      try:
        from devices.pm25 import Pm25
        Pm25(remote_storage, local_storage).publish()
        print("FOUND Pm25")
      except Exception:
        print("NOT FOUND Pm25")

      try:
        from devices.sen5x import Sen5x
        Sen5x(remote_storage, local_storage).publish()
        print("FOUND Sen5x")
      except Exception:
        print("NOT FOUND Sen5x")


if __name__ == '__main__':
  app.run(main)
