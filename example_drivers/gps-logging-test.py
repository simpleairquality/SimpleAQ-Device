#!/usr/bin/env python3

import sys
import time
import calendar

from absl import app, logging
import adafruit_gps
import board
import busio


def gps_setup(gps):
  gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
  gps.send_command(b"PMTK220,1000")


def log_info(gps):
  if gps.timestamp_utc:
    logging.info(f'GPS Time: {gps.timestamp_utc}')
  else:
    logging.info('GPS has no timestamp')

  if gps.has_fix:
    logging.info(f'{gps.latitude}, {gps.longitude}')
  else:
    logging.info('GPS has no fix.')


def main(unused_args):
  i2c = board.I2C()
  gps = adafruit_gps.GPS_GtopI2C(i2c)
  gps_setup(gps)
  last_update = time.monotonic()
  while True:
    gps.update()
    now = time.monotonic()
    if (now - last_update) < 1:
      continue
    else:
      last_update = now
      log_info(gps)


if __name__ == '__main__':
  app.run(main)
