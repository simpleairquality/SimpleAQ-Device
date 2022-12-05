#!/usr/bin/env python3

import psutil
import time

from absl import logging
from . import Sensor


class System(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, display=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    self.display = display
    self.start_time = time.time()

  def publish(self):
    logging.info('Publishing system stats')
    result = False

    # It is actually important that the try_write_to_remote happens before the result, otherwise
    # it will never be evaluated!

    if self.display:
      uptime = time.time() - psutil.boot_time();
      days = int(uptime / (24 * 60 * 60))
      uptime = uptime % (24 * 60 * 60)
      hours = int(uptime / (60 * 60))
      uptime = uptime % (60 * 60)
      minutes = int(uptime / 60)
      
      self.display.write_row("Uptime: {}d + {}h + {}m".format(days, hours, minutes))

    result = self._try_write_to_remote('System', 'device_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_remote('System', 'service_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_remote('System', 'system_time_utc', time.time()) or result

    return result
