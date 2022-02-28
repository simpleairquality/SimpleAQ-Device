#!/usr/bin/env python3

import calendar
import os
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
            'temperature', self.sensor.temperature))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'gas', self.sensor.gas))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'humidity', self.sensor.humidity))
      client.write(
          self.bucket, self.org,
          influxdb_client.Point('BME688').field(
            'pressure', self.sensor.pressure))


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
        client.write(self.bucket, self.org,
            influxdb_client.Point('PM25').field(
              key, val))


class Gps(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    self.gps = adafruit_gps.GPS_GtopI2C(board.I2C())

    def update_gps():
      while True:
        self.gps.update()
        time.sleep(0.5)
    self.update_gps_thread = threading.Thread(target=update_gps, daemon=True)
    self.update_gps_thread.start()

 
  def publish(self):
    logging.info('Publishing GPS data to influx')
    with self.influx.write_api() as client:
      if self.gps.timestamp_utc:
        epoch_seconds = calendar.timegm(self.gps.timestamp_utc)
        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'timestamp_utc', epoch_seconds))
      else:
        logging.warning('GPS has no timestamp data')

      if self.gps.has_fix:
        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'latitude', self.gps.latitude))
        client.write(self.bucket, self.org,
                     influxdb_client.Point('GPS').field(
                       'longitude', self.gps.longitude))
      else:
        logging.warning('GPS has no fix')



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
    sensors.append(Bme688(influx))
    sensors.append(Pm25(influx))
    sensors.append(Gps(influx))
    while True:
      for sensor in sensors:
        sensor.publish()
      time.sleep(interval)


if __name__ == '__main__':
  app.run(main)
