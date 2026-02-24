#!/usr/bin/env python3

from absl import logging
import math
import time
import adafruit_sen6x
import board

from . import Sensor

# Based on the SEN5X driver and adafruit-circuitpython-sen6x library
class Sen6x(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, i2c_transceiver, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)

    # Initialize the SEN6X device using the Adafruit library
    # Note: You may need to specify SEN60, SEN63, SEN65, or SEN66 depending on your hardware
    self.device = adafruit_sen6x.SEN66(board.I2C())
    self.has_transmitted_device_info = False

    # Get device information
    try:
      logging.info("SEN6X Product Name: {}".format(self.device.product_name))
      logging.info("SEN6X Serial Number: {}".format(self.device.serial_number))
      # Version returns a tuple (major, minor)
      version = self.device.version
      logging.info("SEN6X Firmware Version: {}.{}".format(version[0], version[1]))
    except Exception as err:
      logging.warning("Could not retrieve all SEN6X device info: {}".format(err))
 
    # Perform a device reset (reboot firmware)
    self.device.reset()
    # Note: reset() in the Adafruit library already includes appropriate delays
    
    self.name = "SEN6X"

  def read(self):
    if not self.device.data_ready:
      return None 

    # Read measured values -> clears the "data ready" flag
    data = self.device.all_measurements()

    return data

  def publish(self):
    logging.info('Publishing SEN6X data')
    result = False
    status = None  # Initialize status variable
    try:
      # Check for sensor errors
      try:
        status = self.device.device_status
      except Exception as err:
        logging.warning("Could not read SEN6X device status: {}".format(err))
      
      data = self.read()

      if not self.has_transmitted_device_info:
        try:
          version = self.device.version
          result = self._try_write('SEN6X', 'firmware_version', '{}.{}'.format(version[0], version[1])) or result
        except Exception as err:
          self._try_write_error('SEN6X', 'firmware_version', str(err))
          raise err

        try:
          result = self._try_write('SEN6X', 'product_name', self.device.product_name) or result
        except Exception as err:
          self._try_write_error('SEN6X', 'product_name', str(err))
          raise err

        try:
          result = self._try_write('SEN6X', 'serial_number', self.device.serial_number) or result
        except Exception as err:
          self._try_write_error('SEN6X', 'serial_number', str(err))
          raise err

        self.has_transmitted_device_info = True

      if data:
        # NAN values are NOT valid JSON. We will not send anything if a nan value is ever found for any reason.
        # The all_measurements() returns a dict with keys: pm1_0, pm2_5, pm4_0, pm10, humidity, 
        # temperature, voc_index, nox_index, co2
        
        if 'humidity' in data and data['humidity'] is not None and not math.isnan(data['humidity']):
          try:
            result = self._try_write('SEN6X', 'relative_humidity_pct', data['humidity']) or result
            # Report error status if RH&T sensor has issues
            if status and status.rht_sensor_error:
              self._try_write_error('SEN6X', 'relative_humidity_pct', 'RH&T sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'relative_humidity_pct', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'relative_humidity_pct', str(err))
            raise err
            
        if 'temperature' in data and data['temperature'] is not None and not math.isnan(data['temperature']):
          try:
            result = self._try_write('SEN6X', 'temperature_C', data['temperature']) or result
            # Report error status if RH&T sensor has issues
            if status and status.rht_sensor_error:
              self._try_write_error('SEN6X', 'temperature_C', 'RH&T sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'temperature_C', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'temperature_C', str(err))
            raise err
            
        if 'pm1_0' in data and data['pm1_0'] is not None and not math.isnan(data['pm1_0']):
          try:
            result = self._try_write('SEN6X', 'pm1.0_ug_m3', data['pm1_0']) or result
            # Report error status if PM sensor has issues
            if status and status.pm_sensor_error:
              self._try_write_error('SEN6X', 'pm1.0_ug_m3', 'PM sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'pm1.0_ug_m3', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'pm1.0_ug_m3', str(err))
            raise err
            
        if 'pm2_5' in data and data['pm2_5'] is not None and not math.isnan(data['pm2_5']):
          try:
            result = self._try_write('SEN6X', 'pm2.5_ug_m3', data['pm2_5']) or result
            # Report error status if PM sensor has issues
            if status and status.pm_sensor_error:
              self._try_write_error('SEN6X', 'pm2.5_ug_m3', 'PM sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'pm2.5_ug_m3', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'pm2.5_ug_m3', str(err))
            raise err
            
        if 'pm4_0' in data and data['pm4_0'] is not None and not math.isnan(data['pm4_0']):
          try:
            result = self._try_write('SEN6X', 'pm4.0_ug_m3', data['pm4_0']) or result
            # Report error status if PM sensor has issues
            if status and status.pm_sensor_error:
              self._try_write_error('SEN6X', 'pm4.0_ug_m3', 'PM sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'pm4.0_ug_m3', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'pm4.0_ug_m3', str(err))
            raise err
            
        if 'pm10' in data and data['pm10'] is not None and not math.isnan(data['pm10']):
          try:
            result = self._try_write('SEN6X', 'pm10.0_ug_m3', data['pm10']) or result
            # Report error status if PM sensor has issues
            if status and status.pm_sensor_error:
              self._try_write_error('SEN6X', 'pm10.0_ug_m3', 'PM sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'pm10.0_ug_m3', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'pm10.0_ug_m3', str(err))
            raise err
            
        if 'voc_index' in data and data['voc_index'] is not None and not math.isnan(data['voc_index']):
          try:
            result = self._try_write('SEN6X', 'voc_index', data['voc_index']) or result
            # Report error status if gas sensor has issues
            if status and status.gas_sensor_error:
              self._try_write_error('SEN6X', 'voc_index', 'Gas sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'voc_index', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'voc_index', str(err))
            raise err
            
        if 'nox_index' in data and data['nox_index'] is not None and not math.isnan(data['nox_index']):
          try:
            result = self._try_write('SEN6X', 'nox_index', data['nox_index']) or result
            # Report error status if gas sensor has issues
            if status and status.gas_sensor_error:
              self._try_write_error('SEN6X', 'nox_index', 'Gas sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'nox_index', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'nox_index', str(err))
            raise err
            
        # SEN6X specific measurements (CO2) - SEN66 only
        if 'co2' in data and data['co2'] is not None and not math.isnan(data['co2']):
          try:
            result = self._try_write('SEN6X', 'co2_ppm', data['co2']) or result
            # Report error status if CO2 sensor has issues
            if status and status.co2_sensor_2_error:
              self._try_write_error('SEN6X', 'co2_ppm', 'CO2 sensor error - value may be unreliable')
            elif status and status.fan_error:
              self._try_write_error('SEN6X', 'co2_ppm', 'Fan blocked/broken - value may be unreliable')
          except Exception as err:
            self._try_write_error('SEN6X', 'co2_ppm', str(err))
            raise err
            
      else:
        logging.info("Data was not ready for SEN6X.")
    except Exception as err:
      logging.error("Error getting data from SEN6X. Is this sensor correctly installed and the cable attached tightly: " + str(err))
      result = self.name

    return result

  def __enter__(self):
    self.device.start_measurement()

  def __exit__(self, exception_type, exception_value, traceback):
    self.device.stop_measurement()
