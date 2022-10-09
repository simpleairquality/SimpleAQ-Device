#!/usr/bin/env python3

import calendar
import datetime
import dotenv
import os
import time

from absl import logging
from . import Sensor

import board
import adafruit_gps


class Gps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)

    self.interval = interval
    self.has_set_time = False
    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.latitude = float(os.getenv('last_latitude')) if os.getenv('last_latitude') else None
    self.longitude = float(os.getenv('last_longitude')) if os.getenv('last_longitude') else None

    try:
      self.gps = adafruit_gps.GPS_GtopI2C(board.I2C())
      # Turn on everything the module collects.
      self.gps.send_command(b"PMTK314,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0")
      # Update once every second (1000ms)
      self.gps.send_command(b"PMTK220,1000")
    except Exception as err:
      # We raise here because if GPS fails, we're probably getting unuseful data entirely.
      logging.error("Error setting up GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      raise err

  # We automatically update the clock if the drift is greater than the reporting interval.
  # This will serve make sure that the device, no matter how long it's been powered down, reports a reasonably accurate time for measurements when possible.
  # We set the time at most once per run, assuming that the clock drift won't be significant compared to an incorrectly set system time.
  # Note that any change here will be quickly clobbered by NTP should any internet connection become available to the device. 
  def _update_systime(self):
    if not self.has_set_time:
      if self.interval:
        epoch_seconds = None
        try:
          epoch_seconds = calendar.timegm(self.gps.timestamp_utc)
        except Exception as err:
          logging.warning("Error converting GPS timestamp: " + str(err))
          return

        if abs(time.time() - epoch_seconds) > self.interval:
          logging.warning('Setting system clock to ' + datetime.datetime.fromtimestamp(calendar.timegm(self.gps.timestamp_utc)).isoformat() +
                          ' because difference of ' + str(abs(time.time() - epoch_seconds)) +
                          ' exceeds interval time of ' + str(self.interval))
          os.system('date --utc -s %s' % datetime.datetime.fromtimestamp(calendar.timegm(self.gps.timestamp_utc)).isoformat())
          self.timesource.set_time(datetime.datetime.now())
          self.has_set_time = True

  def publish(self):
    logging.info('Publishing GPS data to remote')
    # Yes, recommended behavior is to call update twice.  
    self.gps.update()
    self.gps.update()
    result = False
    try:
      if self.gps.has_fix:
        if self.gps.timestamp_utc:
          self._update_systime()

          # Sometimes the GPS timestamp is invalid.  In that case, don't write it.
          gps_timestamp = None
          try:
            gps_timestamp = calendar.timegm(self.gps.timestamp_utc)
          except Exception as err:
            logging.warning("Error converting GPS timestamp: " + str(err))

          if gps_timestamp:
            # It is actually important that the try_write_to_remote happens before the result, otherwise
            # it will never be evaluated!
            result = self._try_write_to_remote('GPS', 'timestamp_utc', gps_timestamp) or result
        else:
          logging.warning('GPS has no timestamp data')

        if self.gps.latitude and self.gps.longitude:
          # It is actually important that the try_write_to_remote happens before the result, otherwise
          # it will never be evaluated!
          self.latitude = self.gps.latitude
          result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
          self.longitude = self.gps.longitude
          result = self._try_write_to_remote('GPS', 'longitude_degrees', self.longitude) or result

          if self.send_last_known_gps:
            result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 0) or result

          # Save the last-known latitude and longitude if they're available.
          if self.env_file:
            dotenv.set_key(
                self.env_file,
                'last_latitude',
                str(self.latitude))
            dotenv.set_key(
                self.env_file,
                'last_longitude',
                str(self.longitude))
        else:
          if self.send_last_known_gps:
            # If desired, send the last-known GPS values.
            if self.latitude is not None and self.longitude is not None:
              result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
              result = self._try_write_to_remote('GPS', 'longitude_degrees', self.longitude) or result
              result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result

          logging.warning('GPS has no lat/lon data.')
      else:
        logging.warning('GPS has no fix.')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
