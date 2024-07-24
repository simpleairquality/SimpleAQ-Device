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

from absl import logging
from serial import Serial
from pyubx2 import UBXReader, NMEA_PROTOCOL, UBX_PROTOCOL 
from pyubx2.ubxtypes_core import ERR_RAISE
from . import Sensor


class UartNmeaGps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    # Stream represents our connection to the UART.
    self.stream = None
    self.last_error = ''

    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

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
    self.interval = interval

    # Start the read thread before the NMEA reader.  
    # It will only try to read if nmea is set.
    self.nmea = None
    self.stop_reading = threading.Event()
    self.serial_lock = threading.Lock()
    self.read_thread = threading.Thread(target=self._read_gps_data, daemon=True)
    self.read_thread.start()

    # We will try to confirm whether we are getting NMEA data on serial0.
    for setting in os.getenv('uart_serial_baud', '9600;NMEA').split(','):
      try:
        with self.serial_lock:
          baud, mode = setting.split(';')
          logging.info("Attempting to connect to {} GPS on {} with baud rate {}".format(mode, os.getenv('uart_serial_port'), int(baud)))
          self.baud = int(baud)
          if mode == 'NMEA':
            self.mode = NMEA_PROTOCOL
          elif mode == 'UBX':
            self.mode = UBX_PROTOCOL
          else:
            raise Exception("Unsupported GPS protocol:  {}".format(mode))
          
          self._restart_serial()

        # Wait and see if we read any data on the serial port.
        max_retry_count = 15

        for _ in range(max_retry_count):
          if self.has_read_data:
            logging.info("Found {} GPS on {} with baud rate {}!".format(self.mode, os.getenv('uart_serial_port'), self.baud))
            break
          time.sleep(1)

        if self.has_read_data:
          break

        with self.serial_lock:
          self.nmea = None 
          self.stream.close()
          time.sleep(1)
          self.stream = None
 
      except Exception as err:
        # We raise here because if GPS fails, we're probably getting unuseful data entirely.
        logging.error("Unexpected error setting up UART GPS:  " + str(err));

    if not self.has_read_data:
      logging.error("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud', '9600;NMEA')))
      raise Exception("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud', '9600;NMEA'))) 

  def _restart_serial(self):
    if self.stream and self.stream.is_open:
      self.stream.close()
      time.sleep(1)  # https://stackoverflow.com/questions/33441579/io-error-errno-5-with-long-term-serial-connection-in-python

    self.stream = Serial(os.getenv('uart_serial_port'), self.baud, timeout=1)
    # Flush the serial port buffer
    self.stream.reset_input_buffer()
    self.stream.reset_output_buffer()
    # Wait a second for it to equilibrate.
    time.sleep(1)
    self.nmea = UBXReader(self.stream, protfilter=self.mode, quitonerror=ERR_RAISE)

  # Close the port when we shut down.
  def __del__(self):
    self.shutdown()

  def shutdown(self):
    self.stop_reading.set()
    with self.serial_lock:
      if self.stream and self.stream.is_open:
        self.stream.close()
        time.sleep(1)

  # Look that keeps latitude and longitude up-to-date.
  def _read_gps_data(self):
    while not self.stop_reading.is_set():
      try:
        with self.serial_lock:
          # Race condition where we're waiting to read but the serial lock above closes the stream.
          if self.nmea:
            (raw_data, parsed_data) = self.nmea.read()
          else:
            time.sleep(1)
            continue

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
            epoch_seconds = None
            epoch_seconds = calendar.timegm((self.gpsdate.year, self.gpsdate.month, self.gpsdate.day, self.gpstime.hour, self.gpstime.minute, self.gpstime.second))

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

        # This error seems to be a death sentence.  Restart the serial if it happens.
        if 'device reports readiness to read but returned no data' in str(err):
          with self.serial_lock:
            self._restart_serial()

  def publish(self):
    logging.info('Publishing GPS data to remote')

    result = False
    try:
      if not self.has_transmitted_device_info:
        result = self._try_write_to_remote('GPS', 'Model', 'Generic UART NMEA/UBX GPS')
        self.has_transmitted_device_info = True

      if self.altitude:
        result = self._try_write_to_remote('GPS', 'altitude_meters', self.latitude) or result

      if self.latitude and self.longitude and abs(self.latitude) <= 90 and abs(self.longitude) <= 180:
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
