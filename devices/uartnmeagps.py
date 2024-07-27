#!/usr/bin/env python3
import calendar
import datetime
import dotenv
import io
import os
import re
import time
import threading
import sys
from serial import Serial

from absl import logging
from pyubx2 import UBXReader, NMEA_PROTOCOL, UBX_PROTOCOL 
from pyubx2.ubxtypes_core import ERR_RAISE
from . import Sensor


class GPSReader(object):
  def __init__(self, serial, interval, timesource):
    self.nmea = UBXReader(serial, quitonerror=ERR_RAISE)
    self.stop_reading = threading.Event()
    self.read_thread = threading.Thread(target=self._read_gps_data, daemon=True)
    self.serial = serial
    self.timesource = timesource
    self.read_thread.start()
    self.interval = interval

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.altitude = None
    self.latitude = float(os.getenv('last_latitude')) if os.getenv('last_latitude') else None
    self.longitude = float(os.getenv('last_longitude')) if os.getenv('last_longitude') else None
    self.last_good_reading = 0
    self.has_transmitted_device_info = False
    self.gpsdate = None
    self.gpstime = None
    self.has_set_time = False
    self.has_read_data = False
    self.last_error = None

  def __del__(self):
    self.kill()

  def kill(self):
    self.stop_reading.set()

  # Thread that keeps latitude and longitude up-to-date.
  def _read_gps_data(self):
    while not self.stop_reading.is_set():
      try:
        # We accept the possibility that we could get bad data if the stream is shut down while reading
        parsed_data = None
        if self.serial:
          (raw_data, parsed_data) = self.nmea.read()
        else:
          time.sleep(1)

        if parsed_data:
          self.has_read_data = True
          if hasattr(parsed_data, 'alt') and hasattr(parsed_data, 'altUnit'):
            if parsed_data.altUnit in ['m', 'M']:
              self.altitude = parsed_data.alt
          if hasattr(parsed_data, 'lon') and parsed_data.lon:
            self.longitude = parsed_data.lon
            self.last_good_reading = time.time()
          if hasattr(parsed_data, 'lat') and parsed_data.lat:
            self.latitude = parsed_data.lat
            self.last_good_reading = time.time()
          if hasattr(parsed_data, 'date') and hasattr(parsed_data, 'time') and parsed_data.date and parsed_data.time:
            # We can set the system time using the date (with YYYY-MM-DD) and time (HH:MM:SS)
            self.gpsdate = parsed_data.date
            self.gpstime = parsed_data.time

            if not self.has_set_time:
              if self.interval:
                if parsed_data.gpsdate and parsed_data.gpstime:
                  epoch_seconds = calendar.timegm((parsed_data.year, parsed_data.month, parsed_data.day, parsed_data.hour, parsed_data.minute, parsed_data.second))

                  if abs(time.time() - epoch_seconds) > self.interval:
                    logging.warning('Setting system clock to ' + datetime.datetime.fromtimestamp(epoch_seconds).isoformat() +
                                    ' because difference of ' + str(abs(time.time() - epoch_seconds)) +
                                    ' exceeds interval time of ' + str(self.interval))
                    os.system('date --utc -s %s' % datetime.datetime.utcfromtimestamp(epoch_seconds).isoformat())
                    self.timesource.set_time(datetime.datetime.now())
                    self.has_set_time = True
      except Exception as err:
        if str(err) != self.last_error:
          exc_type, exc_obj, exc_tb = sys.exc_info()
          fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
          logging.error("UART GPS Error (duplicates will be suppressed) {}:{}: {}".format(fname, exc_tb.tb_lineno, str(err)))
          self.last_error = str(err)


class UartNmeaGps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    # Stream represents our connection to the UART.
    self.stream = None
    self.last_error = ''
    self.timesource = timesource

    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.interval = interval

    # Start the read thread before the NMEA reader.  
    # It will only try to read if nmea is set.
    self.gpsreader = None

    # We will try to confirm whether we are getting NMEA data on serial0.
    for baud in os.getenv('uart_serial_baud', '9600').split(','):
      try:
        # If somehow we threw an exception, make sure we clean up first.
        if self.gpsreader:
          self.gpsreader.kill()
          self.gpsreader = None

        if self.stream:
          self.stream.close()
          self.stream = None
          time.sleep(0.1)

        logging.info("Attempting to connect to UART GPS on {} with baud rate {}".format(os.getenv('uart_serial_port'), int(baud)))
        self.baud = int(baud)

        # PySerial does not reliably respect my desired baud, or timeout apparently.
        os.system('stty -F {} {}'.format(os.getenv('uart_serial_port'), self.baud))
        time.sleep(0.1)

        self.stream = Serial(os.getenv('uart_serial_port'), self.baud, timeout=1)
        self.stream.reset_input_buffer()
        self.stream.reset_output_buffer()
        self.gpsreader = GPSReader(self.stream, self.interval, self.timesource)
 
        # Wait and see if we read any data on the serial port.
        max_retry_count = 15

        for _ in range(max_retry_count):
          if self.has_read_data:
            logging.info("Found UART GPS on {} with baud rate {}!".format(os.getenv('uart_serial_port'), self.baud))
            break
          time.sleep(1)

        if self.has_read_data:
          break

        # Clean up if we didn't read anything.
        self.gpsreader.kill()
        self.gpsreader = None
        self.stream.close()
        time.sleep(1)
        self.stream = None
      except Exception as err:
        # We raise here because if GPS fails, we're probably getting unuseful data entirely.
        logging.error("Unexpected error setting up UART GPS:  " + str(err));

    if not self.has_read_data:
      logging.error("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud', '9600;NMEA')))
      raise Exception("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud', '9600;NMEA'))) 

  # Close the port when we shut down.
  def __del__(self):
    if self.gpsreader:
      self.gpsreader.kill()
      self.gpsreader = None

    if self.stream and self.stream.is_open:
      self.stream.close()
      self.stream = None

  def publish(self):
    logging.info('Publishing GPS data to remote')

    result = False
    try:
      if not self.has_transmitted_device_info:
        result = self._try_write_to_remote('GPS', 'Model', 'Generic UART NMEA/UBX GPS')
        self.has_transmitted_device_info = True

      if self.gpsreader.altitude:
        result = self._try_write_to_remote('GPS', 'altitude_meters', self.gpsreader.latitude) or result

      if self.gpsreader.latitude and self.gpsreader.longitude and abs(self.gpsreader.latitude) <= 90 and abs(self.gpsreader.longitude) <= 180:
        result = self._try_write_to_remote('GPS', 'latitude_degrees', self.gpsreader.latitude) or result
        result = self._try_write_to_remote('GPS', 'longitude_degrees', self.gpsreader.longitude) or result

        # Choose 10 seconds as an acceptable staleness.
        if time.time() - self.gpsreader.last_good_reading < 10:
          result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 0) or result

          # Save the last-known latitude and longitude if they're available.
          if self.env_file:
            dotenv.set_key(
                self.env_file,
                'last_latitude',
                str(self.gpsreader.latitude))
            dotenv.set_key(
                self.env_file,
                'last_longitude',
                str(self.gpsreader.longitude))
        else:
          result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result
      else:
        if self.gpsreader.send_last_known_gps:
          # If desired, send the last-known GPS values.
          if self.gpsreader.latitude is not None and self.gpsreader.longitude is not None:
            result = self._try_write_to_remote('GPS', 'latitude_degrees', self.gpsreader.latitude) or result
            result = self._try_write_to_remote('GPS', 'longitude_degrees', self.gpsreader.longitude) or result
            result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result

        logging.warning('GPS has no lat/lon data.')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
