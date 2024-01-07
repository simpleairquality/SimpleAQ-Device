#!/usr/bin/env python3

import calendar
import datetime
import dotenv
import io
import os
import re
import time
import threading

from absl import logging
from serial import Serial
from pynmeagps import NMEAReader 
from . import Sensor


class UartNmeaGps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    # Stream represents our connection to the UART.
    self.stream = None

    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.latitude = float(os.getenv('last_latitude')) if os.getenv('last_latitude') else None
    self.longitude = float(os.getenv('last_longitude')) if os.getenv('last_longitude') else None
    self.last_good_reading = 0
    self.has_transmitted_device_info = False

    self.has_read_data = False

    # We will try to confirm whether we are getting NMEA data on serial0.
    try:
      self.stream = Serial(os.getenv('uart_serial_port'), int(os.getenv('uart_serial_baud', '9600')), timeout=5)
      self.nmea = NMEAReader(stream)

      self.read_thread = threading.Thread(target=self._read_gps_data, daemon=True)
      self.read_thread.start()

      # Wait and see if we read any data on the serial port.
      time.sleep(2)

      if not self.has_read_data:
        raise Exception("No NMEA GPS data could be read on port {} at baud {}".format(os.getenv('uart_serial_port'), int(os.getenv('uart_serial_baud', '9600'))))
    except Exception as err:
      # We raise here because if GPS fails, we're probably getting unuseful data entirely.
      logging.error("Error setting up UART GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      raise err

  # Close the port when we shut down.
  def __del__(self):
    if self.stream:
      self.stream.close()

  # Look that keeps latitude and longitude up-to-date.
  # TODO:  We no longer auto-set system time from GPS time.  We should re-add that maybe.
  # TODO:  There is other data here too.  Maybe also save that.  hMSL in particular seems interesting.
  def _read_gps_data(self):
    while True:
      try:
        (raw_data, parsed_data) = self.name.read()
        self.has_read_data = True

        # TODO:  pynmeagps does have 'time', from which we should be able to set system time as before.
        if hasattr(parsed_data, 'lon') and parsed_data.lon:
          self.longitude = parsed_data.lon
          self.last_good_reading = time.time()
        if hasattr(parsed_data, 'lat') and parsed_data.lat:
          self.latitude = parsed_data.lat
          self.last_good_reading = time.time()
      except Exception as err:
        logging.error("UART GPS Error: {}".format(str(err)))

  def publish(self):
    logging.info('Publishing GPS data to remote')

    result = False
    try:
      if not self.has_transmitted_device_info:
        result = self._try_write_to_remote('GPS', 'Model', self.device)
        self.has_transmitted_device_info = True

      if self.latitude and self.longitude and abs(gps_latitude) <= 90 and abs(gps_longitude) <= 180:
        result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
        result = self._try_write_to_remote('GPS', 'longitude_degrees', self.longitude) or result

        # Choose 10 seconds as an acceptable staleness.
        if time.time() - self.last_good_reading < 10:
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
          result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result
      else:
        if self.send_last_known_gps:
          # If desired, send the last-known GPS values.
          if self.latitude is not None and self.longitude is not None:
            result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
            result = self._try_write_to_remote('GPS', 'longitude_degrees', self.longitude) or result
            result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result

        logging.warning('GPS has no lat/lon data.')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
