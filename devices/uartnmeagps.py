#!/usr/bin/env python3
import gpsd

import datetime
import dotenv
import os
import time
import sys
from absl import logging
from . import Sensor


class UartNmeaGps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    # Stream represents our connection to the UART.
    self.timesource = timesource
    self.has_transmitted_device_info = False
    self.name = "UARTNMEAGPS"
    self.has_set_time = False

    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.interval = interval

    self.last_known_latitude = os.getenv('last_latitude')
    self.last_known_longitude = os.getenv('last_longitude')

    try:
      gpsd.connect()
      packet = gpsd.get_current()
    except Exception as err:
      logging.error("UARTNMEAGPS could not connect to GPSD: {}".format(str(err)))
      raise Exception("UARTNMEAGPS could not connect to GPSD: {}".format(str(err)))

  def publish(self):
    logging.info('Publishing GPS data to remote')


    result = False
    try:
      if not self.has_transmitted_device_info:
        try:
          result = self._try_write('GPS', 'Model', 'Generic UART NMEA/UBX GPS') or result
          self.has_transmitted_device_info = True
        except Exception as err:
          self._try_write_error('GPS', 'Model', str(err))
          raise err

      packet = gpsd.get_current()

      # See if we actually have a fix.
      if packet.mode >= 2:

        # 3D fix.
        if packet.mode == 3:
          # Write altitude
          try:
            result = self._try_write('GPS', 'altitude_meters', packet.altitude()) or result
          except Exception as err:
            self._try_write_error('GPS', 'altitude_meters', str(err))
            raise err

        # See if we have latitude and longitude
        latitude, longitude = packet.position()

        self.last_known_latitude = latitude
        self.last_known_longitude = longitude

        # Save the last-known lat and lon.
        if self.env_file:
          dotenv.set_key(
              self.env_file,
              'last_latitude',
              str(latitude))
          dotenv.set_key(
              self.env_file,
              'last_longitude',
              str(longitude))

        # Write latitude and longitude
        try:
          result = self._try_write('GPS', 'latitude_degrees', latitude) or result
        except Exception as err:
          self._try_write_error('GPS', 'latitude_degrees', str(err))
          raise err

        try:
          result = self._try_write('GPS', 'longitude_degrees', longitude) or result
        except Exception as err:
          self._try_write_error('GPS', 'longitude_degrees', str(err))
          raise err

        result = self._try_write('GPS', 'last_known_gps_reading', 0) or result

        # Update time if needed.
        if packet.get_time(local_time=False):
          if self.interval:
            epoch_seconds = packet.get_time(local_time=False).timestamp()

            if abs(time.time() - epoch_seconds) > self.interval:
              logging.warning('Setting system clock to ' + datetime.datetime.fromtimestamp(epoch_seconds).isoformat() +
                              ' because difference of ' + str(abs(time.time() - epoch_seconds)) +
                              ' exceeds interval time of ' + str(self.interval))
              os.system('date --utc -s %s' % datetime.datetime.utcfromtimestamp(epoch_seconds).isoformat())
              self.timesource.set_time(datetime.datetime.now())
              self.has_set_time = True
      else:
        logging.warn("UARTNMEAGPS had no fix data available.")

        # If available, send the last-known GPS
        if self.send_last_known_gps:
          # If desired, send the last-known GPS values.
          if self.last_known_latitude is not None and self.last_known_longitude is not None and self.last_known_latitude is not "" and self.last_known_longitude is not "":
            result = self._try_write('GPS', 'latitude_degrees', float(self.last_known_latitude)) or result
            result = self._try_write('GPS', 'longitude_degrees', float(self.last_known_longitude)) or result
            result = self._try_write('GPS', 'last_known_gps_reading', 1) or result

    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name

    return result
