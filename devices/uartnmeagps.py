#!/usr/bin/env python3
import calendar
import datetime
import dotenv
import os
import re
import time
import threading
import subprocess
import sys
from serial import Serial
from io import BufferedReader
from absl import logging
from pyubx2 import UBXReader, ERR_IGNORE
from . import Sensor

# Modified from:  https://github.com/semuconsulting/PyGPSClient/blob/537d48e7fa1526dbb332f3dacaad110d497cc59a/examples/socket_server.py
class GPSReader:
    """
    Stream handler class.
    """

    def __init__(self, serport, baud, timeout, interval, timesource):
        """
        Constructor.
        """

        self._serport = serport
        self._baud = baud
        self._timeout = timeout
        self._serial_object = None
        self._serial_buffer = None
        self._stream_thread = None
        self._stopevent = threading.Event()

        self.timesource = timesource
        self.interval = interval

        # Seed last_latitude and last_longitude from the environment variable, if available.
        self.altitude = None
        self.latitude = float(os.getenv('last_latitude')) if os.getenv('last_latitude') else None
        self.longitude = float(os.getenv('last_longitude')) if os.getenv('last_longitude') else None
        self.last_good_reading = 0
        self.gpsdate = None
        self.gpstime = None
        self.has_set_time = False
        self.has_read_data = False
        self.last_error = None
        self.start_read_thread()

    def start_read_thread(self):
        """
        Start the stream read thread.
        """

        self._stopevent.clear()
        self._stream_thread = threading.Thread(
            target=self._read_thread,
            args=(self._stopevent),
            daemon=True,
        )
        self._stream_thread.start()

    def stop_read_thread(self):
        """
        Stop serial reader thread.
        """

        self._stopevent.set()
        self._stream_thread = None

    def _read_thread(self, stopevent: Event):
        """
        THREADED PROCESS

        Connects to selected data stream and starts read loop.

        :param Event stopevent: thread stop event
        """

        try:
            with Serial(
                self._serport, self._baud, timeout=self._timeout
            ) as self._serial_object:
                stream = BufferedReader(self._serial_object)
                self._readloop(stopevent, stream)

        except Exception as err:
            if str(err) != self.last_error:
                logging.error("UART GPS Error (duplicates will be suppressed) {}".format(str(err)))
                self.last_error = str(err)

    def _readloop(self, stopevent: Event, stream: object):
        """
        Read stream continously until stop event or stream error.

        :param Event stopevent: thread stop event
        :param object stream: data stream
        """
        # pylint: disable=no-self-use

        ubr = UBXReader(
            stream,
            quitonerror=ERR_IGNORE,
            bufsize=DEFAULT_BUFSIZE
        )

        raw_data = None
        parsed_data = None
        while not stopevent.is_set():
            try:
                raw_data, parsed_data = ubr.read()
                if raw_data is not None and parsed_data:
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
                            if self.gpsdate and self.gpstime:
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
                    logging.error("UART GPS Error (duplicates will be suppressed) {}".format(str(err)))
                    self.last_error = str(err)


def get_baud_rate():
  try:
    # Run the stty command and capture the output
    result = subprocess.run(['stty', '-F', '/dev/serial0'], capture_output=True, text=True)
    # Check if the command was successful
    if result.returncode != 0:
      raise Exception(f"When checking baud, stty command failed with error: {result.stderr}")
        
    # Extract the baud rate using awk-like logic in Python
    output = result.stdout
    for line in output.splitlines():
      if 'speed' in line:
        # Split the line and return the second element
        baud_rate = int(line.split()[1])
        return baud_rate

    raise Exception("When checking baud, no baud rate found in result.")
  except Exception as e:
    raise Exception(str(e))


class UartNmeaGps(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)
    # Stream represents our connection to the UART.
    self.last_error = ''
    self.timesource = timesource
    self.has_transmitted_device_info = False
    self.name = "UARTNMEAGPS"

    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.interval = interval

    # Start the read thread before the NMEA reader.  
    # It will only try to read if nmea is set.
    self.gpsreader = None

    # Let's start by ensuring the system baud rate is what we expect.
    self.baud = int(os.getenv('uart_serial_baud', '9600'))

    # PySerial does not reliably respect my desired baud, or timeout apparently.
    # We need to set the baud rate and make sure it took.
    detected_baud = -1
    retry_set_baud = 10

    logging.info("Ensuring that serial port baud is set to {}.".format(self.baud))

    detected_baud = get_baud_rate()
    for _ in range(retry_set_baud):
      if detected_baud == self.baud:
        break
      else:
        os.system('stty -F {} {}'.format(os.getenv('uart_serial_port'), self.baud))
        time.sleep(0.5)
      detected_baud = get_baud_rate()

    logging.info("Attempting to connect to UART GPS on {} with baud rate {}".format(os.getenv('uart_serial_port'), self.baud))

    if detected_baud != self.baud:
      logging.error("Failed to set baud rate. UART NMEA GPS detection will probably fail.")

    self.gpsreader = GPSReader(os.getenv('uart_serial_port'), self.baud, 1, self.interval, self.timesource)
 
    # Wait and see if we read any data on the serial port.
    max_retry_count = 15

    for _ in range(max_retry_count):
      if self.gpsreader.has_read_data:
        logging.info("Found UART GPS on {} with baud rate {}!".format(os.getenv('uart_serial_port'), self.baud))
        break
      time.sleep(1)

    # If we didn't get any data, clean up to the best of our ability.
    if not self.gpsreader or not self.gpsreader.has_read_data:
      self.gpsreader.stop_read_thread()
      logging.error("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud')))
      raise Exception("Could not detect a UART GPS on {} at any setting in {}.".format(os.getenv('uart_serial_port'), os.getenv('uart_serial_baud'))) 

  # Close the port when we shut down.
  def __del__(self):
    if self.gpsreader:
      self.gpsreader.stop_read_thread()

  def publish(self):
    logging.info('Publishing GPS data to remote')

    result = False
    try:
      if not self.has_transmitted_device_info:
        try:
          result = self._try_write('GPS', 'Model', 'Generic UART NMEA/UBX GPS') or result
        except Exception as err:
          self._try_write_error('GPS', 'Model', str(err))
          raise err

        self.has_transmitted_device_info = True

      if self.gpsreader.altitude:
        try:
          result = self._try_write('GPS', 'altitude_meters', self.gpsreader.latitude) or result
        except Exception as err:
          self._try_write_error('GPS', 'altitude_meters', str(err))
          raise err

      if self.gpsreader.latitude and self.gpsreader.longitude and abs(self.gpsreader.latitude) <= 90 and abs(self.gpsreader.longitude) <= 180:
        try:
          result = self._try_write('GPS', 'latitude_degrees', self.gpsreader.latitude) or result
        except Exception as err:
          self._try_write_error('GPS', 'latitude_degrees', str(err))
          raise err

        try:
          result = self._try_write('GPS', 'longitude_degrees', self.gpsreader.longitude) or result
        except Exception as err:
          self._try_write_error('GPS', 'longitude_degrees', str(err))
          raise err


        # Choose 10 seconds as an acceptable staleness.
        if time.time() - self.gpsreader.last_good_reading < 10:
          try:
            result = self._try_write('GPS', 'last_known_gps_reading', 0) or result
          except Exception as err:
            self._try_write_error('GPS', 'last_known_gps_reading', str(err))
            raise err


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
          try:
            result = self._try_write('GPS', 'last_known_gps_reading', 1) or result
          except Exception as err:
            self._try_write_error('GPS', 'last_known_gps_reading', str(err))
            raise err
      else:
        if self.send_last_known_gps:
          # If desired, send the last-known GPS values.
          if self.gpsreader.latitude is not None and self.gpsreader.longitude is not None:
            result = self._try_write('GPS', 'latitude_degrees', self.gpsreader.latitude) or result
            result = self._try_write('GPS', 'longitude_degrees', self.gpsreader.longitude) or result
            result = self._try_write('GPS', 'last_known_gps_reading', 1) or result

        logging.warning('GPS has no lat/lon data.')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name

    return result
