#!/usr/bin/env python3

import contextlib
import json
import os
import time

from absl import app, flags, logging

import dotenv

from devices.system import System
from devices.bme688 import Bme688
from devices.gps import Gps
from devices.pm25 import Pm25

from localstorage.localsqlite import LocalSqlite 
from remotestorage.influxstorage import InfluxStorage

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


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

  # TODO:  Eventually select between this and SimpleAQ API.
  remote_storage_class = InfluxStorage

  # This implicitly creates the database.
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:

    interval = int(os.getenv('simpleaq_interval'))

    # Maybe trigger wlan mode
    if switch_to_wlan():
      logging.warning("Trying to switch to wlan mode.")
      os.system("systemctl start " + os.getenv("wlan_service"))
      # This sleep is essential, or we may switch right back to AP mode because
      # we didn't manage to switch to wlan fast enough.
      time.sleep(30)

    with remote_storage_class(endpoint=os.getenv('influx_server'), organization=os.getenv('influx_org'), bucket=os.getenv('influx_bucket'), token=os.getenv('influx_token')) as remote:
      sensors = []
      # GPS sensor goes first in case it has to set the hardware clock.
      sensors.append(Gps(remote, local_storage, interval))
      sensors.append(Bme688(remote, local_storage))
      sensors.append(Pm25(remote, local_storage))
      sensors.append(System(remote, local_storage))
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
          count = local_storage.countrecords()

          logging.info("Found {} backlog files!".format(count))
 
          with contextlib.closing(local_storage.getcursor()) as cursor:
            # We iterate over the cursor to avoid loading everything into memory at once.
            for data_point in cursor:
              try:
                data_json = json.loads(data_point[1])

                if 'point' in data_json and 'field' in data_json and 'value' in data_json and 'time' in data_json:
                  try:
                    remote.write(data_json)
                  except Exception as err:
                    # Immediately break on Influx errors -- if the connection was lost,
                    # we don't need to retry every file forever.
                    logging.error("Error writing saved data point with id [{}] to Influx: {}".format(data_point[0], str(err)))
                    break

                  # Delete the file once written successfully.
                  local_storage.deleterecord(data_point[0])

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

            logging.info("Wrote {} backlog files.".format(files_written))
 
        # Maybe trigger wlan mode.
        if switch_to_wlan():
          logging.warning("Maintaining wlan mode.")
          os.system("systemctl start " + os.getenv("wlan_service"))
  
        # TODO:  We should probably wait until a specific future time,  instead of sleep.
        time.sleep(interval)
 

if __name__ == '__main__':
  app.run(main)
