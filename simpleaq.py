#!/usr/bin/env python3

import calendar
import datetime
import os
import psutil
import sys
import threading
import time
from pprint import pprint

from absl import app, flags, logging

import board
import busio
from adafruit_pm25.i2c import PM25_I2C
import adafruit_bme680
import adafruit_gps

import influxdb_client
import dotenv

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


class Sensor(object):
  def __init__(self, influx):
    self.influx = influx
    self.bucket = os.getenv('influx_bucket')
    self.org = os.getenv('influx_org')


class Bme688(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    self.sensor = adafruit_bme680.Adafruit_BME680_I2C(board.I2C())
  
  def publish(self):
    logging.info('Publishing Bme688 to influx')
    with self.influx.write_api() as client:
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'temperature_C', self.sensor.temperature).time(datetime.datetime.now()))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'voc_ohms', self.sensor.gas).time(datetime.datetime.now()))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'relative_humidity_pct', self.sensor.humidity).time(datetime.datetime.now()))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'pressure_hPa', self.sensor.pressure).time(datetime.datetime.now()))


class Pm25(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    self.pm25 = PM25_I2C(i2c)

  def read(self):
    try:
      aqdata = self.pm25.read()
    except RuntimeError as e:
      logging.error(f"Couldn't read data from PM2.5 sensor: {e}")
      return {}
    return aqdata

  
  def publish(self):
    logging.info('Publishing PM2.5 to influx')
    with self.influx.write_api() as client:
      aqdata = self.read()

      for key, val in aqdata.items():
        influx_key = key
        if influx_key.startswith('particles'):
          influx_key += " per dL"
        if influx_key.endswith('env'):
          influx_key += " ug per m3"
        if influx_key.endswith('standard'):
          influx_key += " ug per m3"
        client.write(self.bucket, self.org,
            influxdb_client.Point('PM25').field(
              influx_key, val).time(datetime.datetime.now()))


class Gps(Sensor):
  def __init__(self, influx, interval=None):
    super().__init__(influx)
    self.gps = adafruit_gps.GPS_GtopI2C(board.I2C())
    self.interval = interval
    self.has_set_time = False

    def update_gps():
      while True:
        self.gps.update()
        time.sleep(0.5)
    self.update_gps_thread = threading.Thread(target=update_gps, daemon=True)
    self.update_gps_thread.start()

  # We automatically update the clock if the drift is greater than the reporting interval.
  # This will serve make sure that the device, no matter how long it's been powered down, reports a reasonably accurate time for measurements when possible.
  # We set the time at most once per run, assuming that the clock drift won't be significant compared to an incorrectly set system time.
  # Note that any change here will be quickly clobbered by NTP should any internet connection become available to the device. 
  def _update_systime(self):
    if not self.has_set_time:
      if self.interval:
        epoch_seconds = calendar.timegm(self.gps.timestamp_utc)

        if abs(time.time() - epoch_seconds) > self.interval:
          logging.warning('Setting system clock to ' + datetime.datetime.fromtimestamp(calendar.timegm(self.gps.timestamp_utc)).isoformat() +
                          ' because difference of ' + str(abs(time.time() - epoch_seconds)) +
                          ' exceeds interval time of ' + str(self.interval))
          os.system('date --utc -s %s' % datetime.datetime.fromtimestamp(calendar.timegm(self.gps.timestamp_utc)).isoformat())
          self.has_set_time = True

  def publish(self):
    logging.info('Publishing GPS data to influx')
    with self.influx.write_api() as client:
      if self.gps.timestamp_utc:
        self._update_systime()

        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'timestamp_utc', calendar.timegm(self.gps.timestamp_utc)).time(datetime.datetime.now()))
      else:
        logging.warning('GPS has no timestamp data')

      if self.gps.has_fix:
        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'latitude_degrees', self.gps.latitude).time(datetime.datetime.now()))
        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'longitude_degrees', self.gps.longitude).time(datetime.datetime.now()))
      else:
        logging.warning('GPS has no fix')


class System(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    self.start_time = time.time()

  def publish(self):
    logging.info('Publishing system stats')
    with self.influx.write_api() as client:
      client.write(self.bucket,
                   self.org,
                   influxdb_client.Point('System').field(
                     'device_uptime_sec', time.time() - psutil.boot_time()).time(datetime.datetime.now()))
      client.write(self.bucket,
                   self.org,
                   influxdb_client.Point('System').field(
                     'service_uptime_sec', time.time() - self.start_time).time(datetime.datetime.now()))
      client.write(self.bucket,
                   self.org,
                   influxdb_client.Point('System').field(
                     'system_time_utc', time.time()).time(datetime.datetime.now()))



def connect_to_influx():
  url = os.getenv('influx_server')
  token = os.getenv('influx_token')
  org = os.getenv('influx_org')
  return influxdb_client.InfluxDBClient(url=url, token=token, org=org)


def main(args):
  if (FLAGS.env):
    dotenv.load_dotenv(FLAGS.env)
  else:
    dotenv.load_dotenv()

  interval = int(os.getenv('simpleaq_interval'))

  with connect_to_influx() as influx:
    sensors = []
    # GPS sensor goes first in case it has to set the hardware clock.
    sensors.append(Gps(influx, interval))
    sensors.append(Bme688(influx))
    sensors.append(Pm25(influx))
    sensors.append(System(influx))
    while True:
      for sensor in sensors:
        sensor.publish()
      time.sleep(interval)


if __name__ == '__main__':
  app.run(main)
