#!/usr/bin/env python3

import psutil
import time

from absl import logging
from . import Sensor


class System(Sensor):
  def __init__(self, remotestorage, localstorage):
    super().__init__(remotestorage, localstorage)
    self.start_time = time.time()

  def publish(self):
    logging.info('Publishing system stats')
    result = False

    # It is actually important that the try_write_to_remote happens before the result, otherwise
    # it will never be evaluated!

    result = self._try_write_to_remote('System', 'device_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_remote('System', 'service_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_remote('System', 'system_time_utc', time.time()) or result

    return result
