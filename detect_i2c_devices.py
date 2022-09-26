#!/usr/bin/env python3

import contextlib
import os
import sqlite3

from absl import app, flags, logging

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import dotenv

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


def connect_to_influx():
  url = os.getenv('influx_server')
  token = os.getenv('influx_token')
  org = os.getenv('influx_org')
  return influxdb_client.InfluxDBClient(url=url, token=token, org=org)


# This program loads environment variables only on boot.
# If the environment variables change for any reason, the systemd service
# will have to be restarted.
def main(args):
  if (FLAGS.env):
    dotenv.load_dotenv(FLAGS.env)
  else:
    dotenv.load_dotenv()

  # Make sure there's a place to actually put the backlog database if necessary.
  os.makedirs(os.path.dirname(os.getenv("sqlite_db_path")), exist_ok=True)

  # This implicitly creates the database.
  with contextlib.closing(sqlite3.connect(os.getenv("sqlite_db_path"))) as db_conn:

    # OK, we need a table to store backlog data if it doesn't exist.
    with contextlib.closing(db_conn.cursor()) as cursor:
      cursor.execute("CREATE TABLE IF NOT EXISTS data(id INTEGER PRIMARY KEY AUTOINCREMENT, json TEXT)")
      db_conn.commit()

    interval = int(os.getenv('simpleaq_interval'))

    with connect_to_influx() as influx:
      try:
        from devices.system import System
        System(influx, db_conn).publish()
        print("FOUND System")
      except Exception:
        print("NOT FOUND System")

      try:
        from devices.bme688 import Bme688
        Bme688(influx, db_conn).publish()
        print("FOUND Bme688")
      except Exception:
        print("NOT FOUND Bme688")

      try:
        from devices.gps import Gps
        Gps(influx, db_conn).publish()
        print("FOUND Gps")
      except Exception:
        print("NOT FOUND Gps")

      try:
        from devices.pm25 import Pm25
        Pm25(influx, db_conn).publish()
        print("FOUND Pm25")
      except Exception:
        print("NOT FOUND Pm25")

if __name__ == '__main__':
  app.run(main)
