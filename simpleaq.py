#!/usr/bin/env python3

import contextlib
import datetime
import json
import os
import time
import RPi.GPIO as GPIO
import subprocess

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
from devices.pcbartists_decibel import PCBArtistsDecibel 
from devices.uartnmeagps import UartNmeaGps

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

def do_graceful_reboot():
  if os.path.exists(os.getenv("reboot_status_file")):
    os.remove(os.getenv("reboot_status_file"))
    return True
  return False

def do_graceful_system_reboot():
  if os.path.exists(os.getenv("reboot_status_file") + '_system'):
    os.remove(os.getenv("reboot_status_file") + '_system')
    return True
  return False

# Enumerate the list of supported devices here.
device_map = {
    'system': System,
    'bme688': Bme688,
    'bmp3xx': Bmp3xx,
    'uartnmeagps': UartNmeaGps,
    'gps': Gps,
    'pm25': Pm25,
    'sen5x': Sen5x,
    'dfrobotmultigas00': DFRobotMultiGas00,
    'dfrobotmultigas01': DFRobotMultiGas01,
    'dfrobotmultigas10': DFRobotMultiGas10,
    'dfrobotmultigas11': DFRobotMultiGas11,
    'pcbartistsdecibel': PCBArtistsDecibel
}

priority_devices = ['gps', 'dfrobotgps', 'uartnmeagps']

# Find the set of devices that are installed in this system.
def detect_devices(env_file):
  detected_devices = set()
  test_timesource = SystemTimeSource()

  # Figure out what devices are connected.
  with contextlib.closing(LocalDummy()) as local_storage:
    with DummyStorage() as remote_storage:
      with LinuxI2cTransceiver(os.getenv('i2c_bus')) as i2c_transceiver:
        for name, device in device_map.items():
          device_object = None
          try:
            device_object = device(remotestorage=remote_storage, localstorage=local_storage, i2c_transceiver=i2c_transceiver, timesource=test_timesource, env_file=env_file, log_errors=False)
            device_object.publish()
            detected_devices.add(name)
            logging.info("Detected device: {}".format(name))
          except Exception:
            logging.info("Device not detected: {}".format(name))
          finally:
            if device_object:
              del device_object

  # Get the existing devices
  current_devices = set(os.getenv('detected_devices').split(','))

  # Now let's see if these are the same devices listed in the environment variables.
  # If a file is provided, then we set and reboot.
  if env_file and current_devices != detected_devices:
    dotenv.set_key(
        env_file,
        'detected_devices',
        ','.join(detected_devices))

    os.environ['detected_devices'] = ','.join(detected_devices)

    # Restart the hostap service so that it reads correctly.
    os.system('systemctl restart {}'.format(os.getenv('hostap_config_service')))

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


def attempt_reset_i2c_bus(bus_number):
  # Attempt to detect bus stuckness.
  logging.info("Checking for stuck bus condition.")

  start_time = time.time()
  os.system('i2cdetect -y {}'.format(bus_number))
  end_time = time.time()

  # This generally completes almost immediately.  
  # If it took longer than a second, we should try resetting.
  if end_time - start_time > 1:
    logging.info("The I2C bus appears to be stuck.  Device should be power cycled.")
    return True
  return False

# This program loads environment variables only on boot.
# If the environment variables change for any reason, the systemd service
# will have to be restarted.
def main(args):
  # TODO:  Allow this to be configurable.
  #        Also, it would be better if we just used i2c_transceiver everywhere instead of this.
  if (FLAGS.env):
    dotenv.load_dotenv(FLAGS.env)
  else:
    dotenv.load_dotenv()

  # Attempt to avoid rare I2C bus error.
  i2c_bus_stuck = False
  if os.getenv('i2c_bus_number'):
    i2c_bus_stuck = attempt_reset_i2c_bus(int(os.getenv('i2c_bus_number')))

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

  do_system_reboot = False

  # This implicitly creates the database.
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:

    interval = int(os.getenv('simpleaq_interval'))

    with remote_storage_class(endpoint=os.getenv('influx_server'), organization=os.getenv('influx_org'), bucket=os.getenv('influx_bucket'), token=os.getenv('influx_token')) as remote:
      with LinuxI2cTransceiver(os.getenv('i2c_bus')) as i2c_transceiver:
        sensors = []

        for device_object in device_objects:
          try:
            sensor = device_object(remotestorage=remote,
                                   localstorage=local_storage,
                                   timesource=timesource,
                                   interval=interval,
                                   i2c_transceiver=i2c_transceiver,
                                   log_errors=True,
                                   env_file=FLAGS.env,
                                   send_last_known_gps=send_last_known_gps)
            sensors.append(sensor)
          except Exception as err:
            logging.error("Failure initializing detected device: {}".format(str(err)))
            logging.warning("SimpleAQ service will restart now.")
            return 1

        last_write_succeeded = True

        # This enteres a guaranteed-closing context manager for every sensors.
        # The Sen5X, for instance, requires that start_measurement is started at the beginning of a run and exited at the end.
        # Most of the others are no-ops.
        with contextlib.ExitStack() as stack:
          for sensor in sensors:
            stack.enter_context(sensor)

          do_reboot = False
          while not do_reboot and not do_system_reboot:
            timesource.set_time(datetime.datetime.now())
            result_failure = [sensor.publish() for sensor in sensors]

            if any(result_failure):
              # We only report errors, we do not take the entire unit offline if a few things are malfunctioning.
              # Errors will continue to be logged and saved.
              system_device = System(remotestorage=remote, localstorage=local_storage, timesource=timesource, log_errors=True) 
              system_device._try_write("System", "error", "Devices reported errors: " + ','.join([r for r in result_failure if r]))
            elif i2c_bus_stuck:
              system_device = System(remotestorage=remote, localstorage=local_storage, timesource=timesource, log_errors=True)
              system_device._try_write("System", "error", "I2C bus stuckness was detected, and this device should be unplugged and plugged back in again.")

            # All data is written exclusively from local storage.
            logging.info("Getting rows from local storage")
            publish_rows = local_storage.getrecent(int(os.getenv("max_backlog_writes")))
            data_json = [row[1] for row in publish_rows]

            logging.info("Attempting to write {} data points to remote.".format(len(data_json)))
            # We'll try to write them in one single batch.
            if data_json:
              try:
                remote.write(data_json)
 
                # We succeeded in writing the data.  Let's delete it from our local cache.
                logging.info("Deleting written rows.")
                for row in publish_rows:
                  local_storage.deleterecord(row[0])
              except Exception as err:
                logging.error("Failed to write data to remote: {}".format(str(err)))

                if last_write_succeeded:
                    # Let's get a system device and write any useful logging information.
                    # Obviously this won't immediately succeed, but we can later help users debug errors.
                    system_device = System(remotestorage=remote, localstorage=local_storage, timesource=timesource, log_errors=True)

                    try:
                      dmesg_result = subprocess.run(['dmesg | tail -n 100'], shell=True, stdout=subprocess.PIPE)
                      dmesg_string = dmesg_result.stdout.decode('utf-8')

                      simpleaq_result = subprocess.run(['journalctl -u simpleaq.service | tail -n 100'], shell=True, stdout=subprocess.PIPE)
                      simpleaq_string = simpleaq_result.stdout.decode('utf-8')

                      networkmanager_result = subprocess.run(['journalctl -u NetworkManager | tail -n 100'], shell=True, stdout=subprocess.PIPE)
                      networkmanager_string = networkmanager_result.stdout.decode('utf-8')

                      hostap_result = subprocess.run(['journalctl -u hostap_config.service | tail -n 100'], shell=True, stdout=subprocess.PIPE)
                      hostap_string = hostap_result.stdout.decode('utf-8')

                      system_device._try_write("System", "error", "dmesg logs: \n" + dmesg_string +
                                                                  "\n simpleaq logs: \n" + simpleaq_string +
                                                                  "\n networkmanager logs: \n" + networkmanager_string +
                                                                  "\n hostap logs: \n" + hostap_string)
                    except Exception:
                      logging.error("Failed to write error logs: {}".format(str(err)))

                    last_write_succeeded = False

            else:
              logging.info("No data to write!")

            # TODO:  We should probably wait until a specific future time,  instead of sleep.
            time.sleep(interval)

            # We attempt to reboot gracefully, at a time when we've released all of the buses,
            # to prevent inadvertently causing bus stuckness.
            do_reboot = do_graceful_reboot()
            do_system_reboot = do_graceful_system_reboot()

  # Now we've released all of the devices and finalized local storage.  It is safe to do a gracefull reboot.
  if do_reboot:
    logging.info("Detected request for graceful restart.  Restarting SimpleAQ services and hostapd now.")
    os.system('systemctl restart {}'.format(os.getenv('hostap_config_service')))
    os.system('systemctl restart hostapd')

  if do_system_reboot:
    logging.info("Detected request for a system reboot.  Rebooting now.")
    os.system('reboot')
    time.sleep(15)  # Wait 15 seconds.  We don't want SimpleAQ to come back up.

if __name__ == '__main__':
  app.run(main)
