#!/usr/bin/env python3

import psutil
import time

from absl import logging
from . import Sensor


class System(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.start_time = time.time()
    self.name = "System"

  def publish(self):
    logging.info('Publishing system stats')
    result = False

    # It is actually important that the try_write_to_remote happens before the result, otherwise
    # it will never be evaluated!

    try:
      result = self._try_write('System', 'device_uptime_sec', time.time() - psutil.boot_time()) or result
    except Exception as err:
      self._try_write_error('System', 'device_uptime_sec', str(err))

    try:
      result = self._try_write('System', 'service_uptime_sec', time.time() - psutil.boot_time()) or result
    except Exception as err:
      self._try_write_error('System', 'service_uptime_sec', str(err))

    try:
      result = self._try_write('System', 'system_time_utc', time.time()) or result
    except Exception as err:
      self._try_write_error('System', 'system_time_utc', str(err))

    return result
