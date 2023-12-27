#!/usr/bin/env python3

import calendar
import datetime
import dotenv
import os
import time
import smbus

from absl import logging
from . import Sensor

I2C_MODE  = 0x01
UART_MODE = 0x02

GNSS_DEVICE_ADDR = 0x20
I2C_YEAR_H = 0
I2C_YEAR_L = 1
I2C_MONTH = 2
I2C_DATE  = 3
I2C_HOUR  = 4
I2C_MINUTE = 5
I2C_SECOND = 6
I2C_LAT_1 = 7
I2C_LAT_2 = 8
I2C_LAT_X_24 = 9
I2C_LAT_X_16 = 10
I2C_LAT_X_8  = 11
I2C_LAT_DIS  = 12
I2C_LON_1 = 13
I2C_LON_2 = 14
I2C_LON_X_24 = 15
I2C_LON_X_16 = 16
I2C_LON_X_8  = 17
I2C_LON_DIS  = 18
I2C_USE_STAR = 19
I2C_ALT_H = 20
I2C_ALT_L = 21
I2C_ALT_X = 22
I2C_SOG_H = 23
I2C_SOG_L = 24
I2C_SOG_X = 25
I2C_COG_H = 26
I2C_COG_L = 27
I2C_COG_X = 28
I2C_START_GET = 29
I2C_ID = 30
I2C_DATA_LEN_H = 31
I2C_DATA_LEN_L = 32
I2C_ALL_DATA = 33
I2C_GNSS_MODE = 34
I2C_SLEEP_MODE = 35
I2C_RGB_MODE = 36

ENABLE_POWER = 0
DISABLE_POWER = 1

RGB_ON = 0x05
RGB_OFF = 0x02
GPS = 1
BeiDou = 2
GPS_BeiDou = 3
GLONASS = 4
GPS_GLONASS = 5
BeiDou_GLONASS = 6
GPS_BeiDou_GLONASS = 7


class struct_utc_tim:
  def __init__(self):
    self.year=2000
    self.month=1
    self.date=1
    self.hour=0
    self.minute=0
    self.second=0

class struct_lat_lon:
  def __init__(self):
    self.lat_dd = 0
    self.lat_mm = 0
    self.lat_mmmmm = 0
    self.lat_direction = "S"
    self.latitude_degree = 0.00
    self.latitude = 0.00
    self.lon_ddd = 0
    self.lon_mm = 0
    self.lon_mmmmm = 0
    self.lon_direction = "W"
    self.lonitude = 0.00
    self.lonitude_degree = 0.00


class DfrobotGps(Sensor):
  __m_flag   = 0                # mode flag
  __count    = 0                # acquisition count    
  __txbuf        = [0]          # i2c send buffer
  __gnss_all_data  = [0]*1300     # gnss data
  __uart_i2c     =  0

  def __init__(self, remotestorage, localstorage, timesource, interval=None, send_last_known_gps=False, env_file=None, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)

    # i2cbus takes only the integer bus ID.
    self.i2cbus = smbus.SMBus(int(os.getenv('i2c_bus')[-1]))
    self.__uart_i2c = I2C_MODE
    self.__addr = GNSS_DEVICE_ADDR

    self.interval = interval
    self.has_set_time = False
    # If available, we will save last known GPS coordinates to environment variables.
    self.env_file = env_file
    self.send_last_known_gps = send_last_known_gps
    self.has_transmitted_device_info = False

    # Seed last_latitude and last_longitude from the environment variable, if available.
    self.latitude = float(os.getenv('last_latitude')) if os.getenv('last_latitude') else None
    self.longitude = float(os.getenv('last_longitude')) if os.getenv('last_longitude') else None

    self.utc = struct_utc_tim()
    self.lat_lon = struct_lat_lon()

    # Initialize the sensor.  We need to throw if we don't detect this.
    rslt = self.read_reg(I2C_ID, 1)
    time.sleep(0.1)
    if rslt == -1:
      raise Exception("DFRobot GPS not detected.")
    if rslt[0] != GNSS_DEVICE_ADDR:
      raise Exception("DFRobot GPS not detected.")

    # Use all available satellites.
    self.set_gnss(GPS_BeiDou_GLONASS)

    # Enable power.
    self.enable_power()

    # Enable the RGB LED.
    # Yes, this wastes a trivial amount of power but will be good for debugging.
    self.rgb_on()

  def set_gnss(self, mode):
    '''!
      @brief Set GNSS to be used 
      @param mode
      @n   GPS              use gps
      @n   BeiDou           use beidou
      @n   GPS_BeiDou       use gps + beidou
      @n   GLONASS          use glonass
      @n   GPS_GLONASS      use gps + glonass
      @n   BeiDou_GLONASS   use beidou +glonass
      @n   GPS_BeiDou_GLONASS use gps + beidou + glonass
    '''
    self.__txbuf[0] = mode
    self.write_reg(I2C_GNSS_MODE, self.__txbuf)
    time.sleep(0.1)

  def enable_power(self):
    '''!
      @brief Enable gnss power
    '''
    self.__txbuf[0] = ENABLE_POWER
    self.write_reg(I2C_SLEEP_MODE, self.__txbuf)
    time.sleep(0.1)

  def rgb_on(self):
    '''!
      @brief Turn rgb on 
    '''
    self.__txbuf[0] = RGB_ON
    self.write_reg(I2C_RGB_MODE, self.__txbuf)
    time.sleep(0.1)

  def write_reg(self, reg, data):
    max_retries = 5
    for i in range(max_retries):
      try:
        self.i2cbus.write_i2c_block_data(self.__addr, reg, data)
        return
      except:
        logging.error("Write to DFRobot GPS failed: " + str(err))
        time.sleep(1)

  def read_reg(self, reg, len):
    try:
      rslt = self.i2cbus.read_i2c_block_data(self.__addr, reg, len)
    except Exception as err:
      logging.error("Read from DFRobot GPS failed: " + str(err))
      rslt = -1
      
    return rslt

  def get_date(self):
    '''!
      @brief Get date information, year, month, day 
      @return struct_utc_tim type, represents the returned year, month, day
    '''
    rslt = self.read_reg(I2C_YEAR_H, 4)
    if rslt != -1:
      self.utc.year = rslt[0]*256 + rslt[1]
      self.utc.month = rslt[2]
      self.utc.date = rslt[3]
    return self.utc

  def get_utc(self):
    '''!
      @brief Get time information, hour, minute second 
      @return struct_utc_tim type, represents the returned hour, minute, second 
    '''
    rslt = self.read_reg(I2C_HOUR, 3)
    if rslt != -1:
      self.utc.hour = rslt[0]
      self.utc.minute = rslt[1]
      self.utc.second = rslt[2]
    return self.utc

  def get_lat(self):
    '''!
      @brief Get latitude 
      @return struct_lat_lon type, represents the returned latitude 
    '''
    rslt = self.read_reg(I2C_LAT_1, 6)
    if rslt != -1:
      self.lat_lon.lat_dd = rslt[0]
      self.lat_lon.lat_mm = rslt[1]
      self.lat_lon.lat_mmmmm = rslt[2]*65536 + rslt[3]*256 + rslt[4]
      self.lat_lon.lat_direction = chr(rslt[5])
      self.lat_lon.latitude = self.lat_lon.lat_dd*100.0 + self.lat_lon.lat_mm + self.lat_lon.lat_mmmmm/100000.0
      self.lat_lon.latitude_degree = self.lat_lon.lat_dd + self.lat_lon.lat_mm/60.0 + self.lat_lon.lat_mmmmm/100000.0/60.0
      if self.lat_lon.lat_direction == 'S':
        # I am unsure whether the latitude_degree will automatically be negative for southern degrees.
        # It does not for Western longitude so I assume it is not.  This is purely defensive coding.
        self.latitude = -1.0 * abs(self.lat_lon.latitude_degree)
      else:
        self.latitude = self.lat_lon.latitude_degree
 
    return self.latitude

  def get_lon(self):
    '''!
      @brief Get longitude 
      @return struct_lat_lon type, represents the returned longitude 
    '''
    rslt = self.read_reg(I2C_LON_1, 6)
    if rslt != -1:
      self.lat_lon.lon_ddd = rslt[0]
      self.lat_lon.lon_mm = rslt[1]
      self.lat_lon.lon_mmmmm = rslt[2]*65536 + rslt[3]*256 + rslt[4]
      self.lat_lon.lon_direction = chr(rslt[5])
      self.lat_lon.lonitude = self.lat_lon.lon_ddd*100.0 + self.lat_lon.lon_mm + self.lat_lon.lon_mmmmm/100000.0
      self.lat_lon.lonitude_degree = self.lat_lon.lon_ddd + self.lat_lon.lon_mm/60.0 + self.lat_lon.lon_mmmmm/100000.0/60.0
      if self.lat_lon.lon_direction == 'W':
        self.longitude = -1.0 * abs(self.lat_lon.lonitude_degree)
      else:
        self.longitude = self.lat_lon.lonitude_degree

    return self.longitude

  def get_num_sta_used(self):
    '''!
      @brief Get the number of the used satellites 
      @return The number of the used satellites 
    '''
    rslt = self.read_reg(I2C_USE_STAR, 1)
    if rslt != -1:
      return rslt[0]
    else:
      return 0

  def get_alt(self):
    '''!
      @brief Get altitude 
      @return double type, represent the altitude 
    '''
    rslt = self.read_reg(I2C_ALT_H, 3)
    if rslt != -1:
      high = rslt[0]*256 + rslt[1] + rslt[2]/100.0
    else:
      high = None
    return high

  def get_gps_time(self):
    self.get_date()
    self.get_utc()
    return datetime.datetime(self.utc.year, self.utc.month, self.utc.date, self.utc.hour, self.utc.minute, self.utc.second)

  # We automatically update the clock if the drift is greater than the reporting interval.
  # This will serve make sure that the device, no matter how long it's been powered down, reports a reasonably accurate time for measurements when possible.
  # We set the time at most once per run, assuming that the clock drift won't be significant compared to an incorrectly set system time.
  # Note that any change here will be quickly clobbered by NTP should any internet connection become available to the device. 
  def _update_systime(self):
    if not self.has_set_time:
      if self.interval:
        epoch_seconds = None
        gps_time = self.get_gps_time() 

        try:
          epoch_seconds = calendar.timegm(gps_time.timetuple())
        except Exception as err:
          logging.warning("Error converting GPS timestamp: " + str(err))
          return

        if abs(time.time() - epoch_seconds) > self.interval:
          gps_time = self.get_gps_time() 

          logging.warning('Setting system clock to ' + gps_time.isoformat() +
                          ' because difference of ' + str(abs(time.time() - epoch_seconds)) +
                          ' exceeds interval time of ' + str(self.interval))
          os.system('date --utc -s %s' % gps_time.isoformat())
          self.timesource.set_time(datetime.datetime.now())
          self.has_set_time = True

  def publish(self):
    logging.info('Publishing GPS data to remote')
    result = False
    try:
      if not self.has_transmitted_device_info:
        result = self._try_write_to_remote('GPS', 'Model', 'DFRobot Gravity: GNSS GPS BEIDOU Receiver TEL0157')
        self.has_transmitted_device_info = True

      num_satellites = self.get_num_sta_used()
      result = self._try_write_to_remote('GPS', 'number_of_satellites', num_satellites)

      altitude = self.get_alt()
      if altitude is not None:
        result = self._try_write_to_remote('GPS', 'altitude_m', altitude) 

      if num_satellites >= 4:
        self._update_systime()

        gps_time = self.get_gps_time()
        gps_timestamp = calendar.timegm(gps_time.timetuple())

        if gps_timestamp:
          # It is actually important that the try_write_to_remote happens before the result, otherwise
          # it will never be evaluated!
          result = self._try_write_to_remote('GPS', 'timestamp_utc', gps_timestamp) or result
        else:
          logging.warning('GPS has no timestamp data')

        # Avoid flakes in case the reading changes.
        gps_latitude = self.get_lat()
        gps_longitude = self.get_lon()

        if gps_latitude and gps_longitude and abs(gps_latitude) <= 90 and abs(gps_longitude) <= 180:
          # It is actually important that the try_write_to_remote happens before the result, otherwise
          # it will never be evaluated!
          self.latitude = gps_latitude
          result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
          self.longitude = gps_longitude
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
        if self.send_last_known_gps:
          # If desired, send the last-known GPS values.
          if self.latitude is not None and self.longitude is not None:
            result = self._try_write_to_remote('GPS', 'latitude_degrees', self.latitude) or result
            result = self._try_write_to_remote('GPS', 'longitude_degrees', self.longitude) or result
            result = self._try_write_to_remote('GPS', 'last_known_gps_reading', 1) or result

        logging.warning('GPS has no fix.')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result
