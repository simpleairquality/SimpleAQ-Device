#!/usr/bin/env python3

import calendar
import datetime
import json
import os
import psutil
import sys
import threading
import time
from dateutil import parser
from pprint import pprint

from absl import app, flags, logging

import board
import busio
from adafruit_pm25.i2c import PM25_I2C
import adafruit_bme680
import adafruit_gps

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import dotenv

FLAGS = flags.FLAGS
flags.DEFINE_string('env', None, 'Location of an alternate .env file, if desired.')


class Sensor(object):
  def __init__(self, influx):
    self.influx = influx
    self.bucket = os.getenv('influx_bucket')
    self.org = os.getenv('influx_org')

  # Even though we never explicitly create rows, InfluxDB assigns a type
  # when a row is first written.  Apparently, sometimes intended float values are incorrectly
  # interpreted as a int and changing field types after the fact is hard.
  # So let's avoid that hassle entirely.
  def _make_ints_to_float(self, value):
    if isinstance(value, int):
      return float(value)
    return value

  def _try_write_to_influx(self, point, field, value):
    try:
      with self.influx.write_api(write_options=SYNCHRONOUS) as client:
        client.write(
            self.bucket,
            self.org,
            influxdb_client.Point(point).field(
                field, self._make_ints_to_float(value)).time(datetime.datetime.now()))
        return False
    except Exception as err:
      logging.error("Could not write to InfluxDB: " + str(err))

      # If we failed to write, save to disk instead.
      # Need to make sure the path exists first.
      try:
        if not os.path.isdir(os.getenv("data_save_path")):
          os.makedirs(os.getenv("data_save_path"))

        with open(os.path.join(os.getenv("data_save_path"), str(point) + "_" + str(field) + "_" + str(time.time())), "w") as f:
          data_json = {
              'point': point,
              'field': field,
              'value': self._make_ints_to_float(value),
              'time': datetime.datetime.now().isoformat()
          }

          f.write(json.dumps(data_json))

        return True
      except Exception as backup_err:
        # Something has truly gone sideways.  We can't even write backup data.
        logging.error("Error saving data to local disk: " + str(backup_err))
        return True

class Bme688(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    self.sensor = adafruit_bme680.Adafruit_BME680_I2C(board.I2C())

  def publish(self):
    logging.info('Publishing Bme688 to influx')
    result = False
    try:
      # It is actually important that the try_write_to_influx happens before the result, otherwise
      # it will never be evaluated!
      result = self._try_write_to_influx('BME688', 'temperature_C', self.sensor.temperature) or result
      result = self._try_write_to_influx('BME688', 'voc_ohms', self.sensor.gas) or result
      result = self._try_write_to_influx('BME688', 'relative_humidity_pct', self.sensor.humidity) or result
      result = self._try_write_to_influx('BME688', 'pressure_hPa', self.sensor.pressure) or result
    except Exception as err:
      logging.error("Error getting data from BME688.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True
    return result


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
    result = False
    try:
      aqdata = self.read()

      for key, val in aqdata.items():
        influx_key = key
        if influx_key.startswith('particles'):
          influx_key += " per dL"
        if influx_key.endswith('env'):
          influx_key += " ug per m3"
        if influx_key.endswith('standard'):
          influx_key += " ug per m3"
        # It is actually important that the try_write_to_influx happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write_to_influx('PM25', influx_key, val) or result
    except Exception as err:
      logging.error("Error getting data from PM25.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result


class Gps(Sensor):
  def __init__(self, influx, interval=None):
    super().__init__(influx)

    try:
      self.gps = adafruit_gps.GPS_GtopI2C(board.I2C())
      self.interval = interval
      self.has_set_time = False

      def update_gps():
        while True:
          self.gps.update()
          time.sleep(0.5)
      self.update_gps_thread = threading.Thread(target=update_gps, daemon=True)
      self.update_gps_thread.start()
    except Exception as err:
      logging.error("Error setting up GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      raise err

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
    result = False
    try:
      if self.gps.timestamp_utc:
        self._update_systime()

        # It is actually important that the try_write_to_influx happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write_to_influx('GPS', 'timestamp_utc', calendar.timegm(self.gps.timestamp_utc)) or result
      else:
        logging.warning('GPS has no timestamp data')

      if self.gps.has_fix:
        # It is actually important that the try_write_to_influx happens before the result, otherwise
        # it will never be evaluated!
        result = self._try_write_to_influx('GPS', 'latitude_degrees', self.gps.latitude) or result
        result = self._try_write_to_influx('GPS', 'longitude_degrees', self.gps.longitude) or result
      else:
        logging.warning('GPS has no fix')
    except Exception as err:
      logging.error("Error getting data from GPS.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = True

    return result


class System(Sensor):
  def __init__(self, influx):
    super().__init__(influx)
    self.start_time = time.time()

  def publish(self):
    logging.info('Publishing system stats')
    result = False

    # It is actually important that the try_write_to_influx happens before the result, otherwise
    # it will never be evaluated!

    result = self._try_write_to_influx('System', 'device_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_influx('System', 'service_uptime_sec', time.time() - psutil.boot_time()) or result
    result = self._try_write_to_influx('System', 'system_time_utc', time.time()) or result

    return result


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
    sensors.append(Gps(influx, interval))
    sensors.append(Bme688(influx))
    sensors.append(Pm25(influx))
    sensors.append(System(influx))
    while True:
      for sensor in sensors:
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

          if os.path.isdir(os.getenv("data_save_path")) and len(os.listdir(os.getenv("data_save_path"))) > 0:
            logging.info("Found {} backlog files!".format(len(os.listdir(os.getenv("data_save_path")))))

            for f in os.listdir(os.getenv("data_save_path")):
              if os.path.isfile(os.path.join(os.getenv("data_save_path"), f)):
                try:
                  with open(os.path.join(os.getenv("data_save_path"), f)) as fp:
                    data_json = json.load(fp)

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
                        logging.error("Error writing file " + f + " to Influx: " + str(err))
                        break

                      # Delete the file once written successfully.
                      os.remove(os.path.join(os.getenv("data_save_path"), f))
                      files_written += 1
                    else:
                      # Eventually, very many malformed files in this directory would cause unacceptable slowness.
                      logging.warning("Data file " + f + " has missing fields.")
                except Exception as err:
                  logging.error("Error writing saved file [" + f + "] : " + str(err))
              else:
                logging.info("{} is a directory!".format(f))

              # We spread out our writing of backlogs, so as not to spend a long time writing
              # many backups after a long downtime.  We'll catch up eventually.
              if files_written >= int(os.getenv("max_backlog_writes")):
                break

            logging.info("Wrote {} backlog files.".format(files_written))
          else:
            logging.info("None found!")

      # Maybe trigger wlan mode.
      if switch_to_wlan():
        logging.warning("Maintaining wlan mode.")
        os.system("systemctl start " + os.getenv("wlan_service"))

      # TODO:  We should probably wait until a specific future time,  instead of sleep.
      time.sleep(interval)


if __name__ == '__main__':
  app.run(main)
