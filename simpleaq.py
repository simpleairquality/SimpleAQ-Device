#!/usr/bin/env python3

import contextlib
import json
import os
import sqlite3
import time
from dateutil import parser

from absl import app, flags, logging

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import dotenv

from devices.system import System
from devices.bme688 import Bme688
from devices.gps import Gps
from devices.pm25 import Pm25

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


def connect_to_influx():
  url = os.getenv('influx_server')
  token = os.getenv('influx_token')
  org = os.getenv('influx_org')
  return influxdb_client.InfluxDBClient(url=url, token=token, org=org)


def switch_to_wlan():
  if os.path.exists(os.getenv("hostap_status_file")):
    if time.time() - os.path.getmtime(os.getenv("hostap_status_file")) >= int(os.getenv("hostap_retry_interval_sec")):
      os.remove(os.getenv("hostap_status_file"))
      return True
    else:
      return False
  else:
    return True


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

    # Maybe trigger wlan mode
    if switch_to_wlan():
      logging.warning("Trying to switch to wlan mode.")
      os.system("systemctl start " + os.getenv("wlan_service"))
      # This sleep is essential, or we may switch right back to AP mode because
      # we didn't manage to switch to wlan fast enough.
      time.sleep(30)

    with connect_to_influx() as influx:
      sensors = []
      # GPS sensor goes first in case it has to set the hardware clock.
      sensors.append(Gps(influx, db_conn, interval))
      sensors.append(Bme688(influx, db_conn))
      sensors.append(Pm25(influx, db_conn))
      sensors.append(System(influx, db_conn))
      while True:
        result_failure = [sensor.publish() for sensor in sensors]
        if any(result_failure):
          logging.warning("Failed to write some results.  Switching to hostap mode.")

          # Trigger hostapd mode.
          os.system("systemctl start " + os.getenv("ap_service"))

          # Maybe touch a file to indicate the time that we did this.
          if not os.path.exists(os.getenv("hostap_status_file")):
            os.system("touch " + os.getenv("hostap_status_file"))
        else:
          # Write backlog files.
          files_written = 0
          logging.info("Checking for backlog files to write.")

          with contextlib.closing(db_conn.cursor()) as cursor:
            result = cursor.execute("SELECT COUNT(*) FROM data")
            count = result.fetchone()[0]

            logging.info("Found {} backlog files!".format(count))
 
            cursor.execute("SELECT * FROM data")

            # We iterate over the cursor to avoid loading everything into memory at once.
            for data_point in cursor:
              try:
                data_json = json.loads(data_point[1])

                if 'point' in data_json and 'field' in data_json and 'value' in data_json and 'time' in data_json:
                  try:
                    with influx.write_api(write_options=SYNCHRONOUS) as client:
                      client.write(
                          os.getenv('influx_bucket'),
                          os.getenv('influx_org'),
                          influxdb_client.Point(data_json.get('point')).field(
                              data_json.get('field'), data_json.get('value')).time(parser.parse(data_json.get('time'))))
                  except Exception as err:
                    # Immediately break on Influx errors -- if the connection was lost,
                    # we don't need to retry every file forever.
                    logging.error("Error writing saved data point with id [{}] to Influx: {}".format(data_point[0], str(err)))
                    break

                  # Delete the file once written successfully.
                  with contextlib.closing(db_conn.cursor()) as delete_cursor:
                    delete_cursor.execute("DELETE FROM data WHERE id=?", (data_point[0],))
                  files_written += 1
                else:
                  # Eventually, very many malformed files in this directory would cause unacceptable slowness.
                  logging.warning("Data point with id [{}] has missing fields.".format(data_point[0]))

              except Exception as err:
                logging.error("Error writing saved data point with id [{}]: {}".format(data_point[0], str(err)))

              # We spread out our writing of backlogs, so as not to spend a long time writing
              # many backups after a long downtime.  We'll catch up eventually.

              if files_written >= int(os.getenv("max_backlog_writes")):
                break

            # Commit deleted rows.
            db_conn.commit()

            logging.info("Wrote {} backlog files.".format(files_written))
 
        # Maybe trigger wlan mode.
        if switch_to_wlan():
          logging.warning("Maintaining wlan mode.")
          os.system("systemctl start " + os.getenv("wlan_service"))
  
        # TODO:  We should probably wait until a specific future time,  instead of sleep.
        time.sleep(interval)
 

if __name__ == '__main__':
  app.run(main)
