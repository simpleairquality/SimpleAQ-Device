#!/usr/bin/env python3

import contextlib
import datetime
import json
import os
import time

from absl import app, flags, logging

import dotenv

from devices.system import System
from devices.bme688 import Bme688
from devices.bmp3xx import Bmp3xx
from devices.gps import Gps
from devices.pm25 import Pm25
from devices.sen5x import Sen5x
from devices.dfrobot_multigassensor import DFRobotMultiGas00 
from devices.dfrobot_multigassensor import DFRobotMultiGas01
from devices.dfrobot_multigassensor import DFRobotMultiGas10
from devices.dfrobot_multigassensor import DFRobotMultiGas11

from localstorage.localdummy import LocalDummy
from localstorage.localsqlite import LocalSqlite 
from remotestorage.dummystorage import DummyStorage
from remotestorage.influxstorage import InfluxStorage
from remotestorage.simpleaqstorage import SimpleAQStorage

from timesources.systemtimesource import SystemTimeSource
from timesources.synctimesource import SyncTimeSource

from sensirion_i2c_driver import LinuxI2cTransceiver

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


def switch_to_wlan():
  if os.path.exists(os.getenv("hostap_status_file")):
    if time.time() - os.path.getmtime(os.getenv("hostap_status_file")) >= int(os.getenv("hostap_retry_interval_sec")) or time.time() < os.path.getmtime(os.getenv("hostap_status_file")):
      os.remove(os.getenv("hostap_status_file"))
      return True
    else:
      logging.info("Will retry wifi connection in {} seconds ({}/{} waited).".format(
          int(os.getenv("hostap_retry_interval_sec")) - (time.time() - os.path.getmtime(os.getenv("hostap_status_file"))),
          time.time() - os.path.getmtime(os.getenv("hostap_status_file")),
          int(os.getenv("hostap_retry_interval_sec"))))
      return False
  else:
    return True


# Enumerate the list of supported devices here.
device_map = {
    'system': System,
    'bme688': Bme688,
    'bmp3xx': Bmp3xx,
    'gps': Gps,
    'pm25': Pm25,
    'sen5x': Sen5x,
    'dfrobotmultigas00': DFRobotMultiGas00,
    'dfrobotmultigas01': DFRobotMultiGas01,
    'dfrobotmultigas10': DFRobotMultiGas10,
    'dfrobotmultigas11': DFRobotMultiGas11
}

priority_devices = ['gps']

# Find the set of devices that are installed in this system.
def detect_devices(env_file):
  detected_devices = set()
  test_timesource = SystemTimeSource()

  # Figure out what devices are connected.
  with contextlib.closing(LocalDummy()) as local_storage:
    with DummyStorage() as remote_storage:
      with LinuxI2cTransceiver(os.getenv('i2c_bus')) as i2c_transceiver:
        for name, device in device_map.items():
          try:
            device(remotestorage=remote_storage, localstorage=local_storage, i2c_transceiver=i2c_transceiver, timesource=test_timesource).publish()
            detected_devices.add(name)
            logging.info("Detected device: {}".format(name))
          except Exception:
            logging.info("Device not detected: {}".format(name))

  # Get the existing devices
  current_devices = set(os.getenv('detected_devices').split(','))

  # Now let's see if these are the same devices listed in the environment variables.
  # If a file is provided, then we set and reboot.
  if env_file and current_devices != detected_devices:
    dotenv.set_key(
        env_file,
        'detected_devices',
        ','.join(detected_devices))

    # Reboot
    os.system('reboot')

  # Let's make sure that if any priority devices were detected, they are listed first.
  device_objects = []

  for priority_device in priority_devices:
    if priority_device in detected_devices:
      device_objects.append(device_map[priority_device])
      detected_devices.remove(priority_device)

  # Ok, add the rest.
  for device in detected_devices:
   device_objects.append(device_map[device])

  return device_objects


# This program loads environment variables only on boot.
# If the environment variables change for any reason, the systemd service
# will have to be restarted.
def main(args):
  if (FLAGS.env):
    dotenv.load_dotenv(FLAGS.env)
  else:
    dotenv.load_dotenv()

  device_objects = detect_devices(FLAGS.env)

  remote_storage_class = None
  timesource = None
  send_last_known_gps = False
  if os.getenv('endpoint_type') == 'INFLUXDB':
    remote_storage_class = InfluxStorage
    timesource = SystemTimeSource()
    send_last_known_gps = False
  else:
    remote_storage_class = SimpleAQStorage
    timesource = SyncTimeSource()
    send_last_known_gps = True

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
      with LinuxI2cTransceiver(os.getenv('i2c_bus')) as i2c_transceiver:
        sensors = []

        for device_object in device_objects:
          sensors.append(device_object(remotestorage=remote,
                                       localstorage=local_storage,
                                       timesource=timesource,
                                       interval=interval,
                                       i2c_transceiver=i2c_transceiver,
                                       env_file=FLAGS.env,
                                       send_last_known_gps=send_last_known_gps))

        # This enteres a guaranteed-closing context manager for every sensors.
        # The Sen5X, for instance, requires that start_measurement is started at the beginning of a run and exited at the end.
        # Most of the others are no-ops.
        with contextlib.ExitStack() as stack:
          for sensor in sensors:
            stack.enter_context(sensor)
 
          while True:
            timesource.set_time(datetime.datetime.now())
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
              logging.warning("Switching to wlan mode.")
              # This shouldn't be necessary, but we found that sometimes the systemd-networkd DHCP server stalls
              # when we're bringing the wlan up and down.  This brings it back.  See issue #55.
              os.system("service systemd-networkd restart")
              time.sleep(15)  # 15 second cooldown for systemd-networkd to restart.
              os.system("systemctl start " + os.getenv("wlan_service"))
  
            # TODO:  We should probably wait until a specific future time,  instead of sleep.
            time.sleep(interval)
 

if __name__ == '__main__':
  app.run(main)
