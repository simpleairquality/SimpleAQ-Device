#!/usr/bin/env python3

import calendar
import datetime
import json
import os
import sys
import threading
import time

from absl import app, flags, logging

import board
import busio
from adafruit_pm25.i2c import PM25_I2C
import adafruit_bme680
import adafruit_gps

import dotenv

dotenv.load_dotenv()
FLAGS = flags.FLAGS


class Sensor(object):
  def __init__(self, sensor_name):
    self.bucket = os.getenv('influx_bucket')
    self.org = os.getenv('influx_org')
    self.out_dir = os.getenv('data_directory')
    self.sensor_name = sensor_name

  def output_file(self):
    timeslug = datetime.datetime.now().strftime('%Y-%m-%d')
    return f'{self.data_directory}/simpleaq_{timeslug}.json'

  def write(self, field, value):
    packet = {
        'bucket': self.bucket,
        'org': self.org,
        'sensor': self.sensor_name,
        'field': field,
        'value': value,
        'timestamp': datetime.datetime.now().timestamp(),
        }
    logging.info(f'Writing packet: {packet}')
    with open(self.output_file(), 'a') as f:
      f.write(json.dumps(packet) + '\n')


class Bme688(Sensor):
  def __init__(self):
    super().__init__(sensor_name='BME688')
    self.sensor = adafruit_bme680.Adafruit_BME680_I2C(board.I2C())
  
  def save_record(self):
    logging.info('Saving Bme688 to log')
    self.write('temperature', self.sensor.temperature)
    self.write('gas', self.sensor.gas)
    self.write('humidity', self.sensor.humidity)
    self.write('pressure', self.sensor.pressure)


class Pm25(Sensor):
  def __init__(self):
    super().__init__(sensor_name='PM25')
    i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
    self.pm25 = PM25_I2C(i2c)

  def read(self):
    try:
      aqdata = self.pm25.read()
    except RuntimeError as e:
      logging.error(f"Couldn't read data from PM2.5 sensor: {e}")
      return {}
    return aqdata

  
  def save_record(self):
    logging.info('Saving PM2.5 to log')
    for key, val in self.read().items():
      self.write(key, val)


class Gps(Sensor):
  def __init__(self):
    super().__init__('GPS')
    self.gps = adafruit_gps.GPS_GtopI2C(board.I2C())

    def update_gps():
      while True:
        self.gps.update()
        time.sleep(0.5)
    self.update_gps_thread = threading.Thread(target=update_gps, daemon=True)
    self.update_gps_thread.start()

 
  def save_record(self):
    logging.info('Saving GPS data to log')
    gpstime = self.gps.timestamp_utc
    if gpstime and gpstime.tm_year:
      epoch_seconds = calendar.timegm(gpstime)
      self.write('timestamp_utc', epoch_seconds)
    else:
      logging.warning('GPS has no timestamp data')

    if self.gps.has_fix:
      self.write('latitude', self.gps.latitude)
      self.write('longitude', self.gps.longitude)
    else:
      logging.warning('GPS has no fix')


def main(args):
  if len(args) != 1:
    sys.exit(f'Usage: {args[0]}')

  interval = int(os.getenv('simpleaq_interval'))

  sensors = [Bme688(), Pm25(), Gps()]
  while True:
    for sensor in sensors:
      try:
        sensor.save_record()
      except Exception as e:
        logging.error(f'Error saving data for {sensor}: {e}')
    time.sleep(interval)


if __name__ == '__main__':
  app.run(main)
