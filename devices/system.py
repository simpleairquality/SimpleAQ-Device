#!/usr/bin/env python3

import psutil
import time

from absl import logging
from . import Sensor


class System(Sensor):
  def __init__(self, influx, connection):
    super().__init__(influx, connection)
    self.start_time = time.time()

  def publish(self):
    logging.info('Publishing system stats')
    result = False

    # It is actually important that the try_write_to_influx happens before the result, otherwise
    # it will never be evaluated!

    result = self._try_write_to_influx('System', 'device_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_influx('System', 'service_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_influx('System', 'system_time_utc', time.time()) or result

    return result
