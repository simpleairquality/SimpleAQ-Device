#!/usr/bin/env python3

from absl import logging
import math
import time
from struct import unpack
from sensirion_i2c_driver import I2cConnection, LinuxI2cTransceiver
from sensirion_i2c_sen5x import Sen5xI2cDevice
from sensirion_i2c_sen5x.commands.generated import Sen5xI2cCmdBase

from . import Sensor

# Stop asking for raw signals after this many failures in a row (e.g. a sensor
# firmware without the command), so a missing feature can't spam the log.
RAW_SIGNAL_MAX_FAILURES = 3


class Sen5xI2cCmdReadMeasuredRawValues(Sen5xI2cCmdBase):
  """Read Measured Raw Values (0x03D2), which sensirion-i2c-sen5x 0.1.1 lacks.

  Returns raw RH (x100), raw T (x200), raw VOC (ticks) and raw NOx (ticks).
  Unknown values are 0x7FFF (int16) or 0xFFFF (uint16): SEN50 has no VOC or
  NOx, SEN54 has no NOx, and NOx is unknown for ~11 s after a reset.
  Format: Sensirion, "SEN5x: Read RHT, VOC and NOx RAW signals".
  """

  def __init__(self):
    super().__init__(
        command=0x03D2,
        tx_data=None,
        rx_length=12,
        read_delay=0.02,
        timeout=0,
        post_processing_time=0.0,
    )

  def interpret_response(self, data):
    checked_data = Sen5xI2cCmdBase.interpret_response(self, data)
    return unpack(">hhHH", checked_data[0:8])

# Based on https://sensirion.github.io/python-i2c-sen5x/quickstart.html#linux-i2c-bus-example
class Sen5x(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, i2c_transceiver, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)

    self.i2c_transceiver = i2c_transceiver
    self.device = Sen5xI2cDevice(I2cConnection(i2c_transceiver))
    self.has_transmitted_device_info = False
    self.raw_signal_failures = 0

    logging.info("SEN5X Version: {}".format(self.device.get_version()))
    logging.info("SEN5X Product Name: {}".format(self.device.get_product_name()))
    logging.info("SEN5X Serial Number: {}".format(self.device.get_serial_number()))
 
    # Perform a device reset (reboot firmware)
    self.device.device_reset()
    self.name = "SEN5X"

  def read(self):
    if not self.device.read_data_ready():
      return None 

    # Read measured values -> clears the "data ready" flag
    values = self.device.read_measured_values()

    return values

  def read_raw_gas_signals(self):
    """Raw VOC and NOx signals in ticks, None where the sensor has none."""
    _, _, raw_voc, raw_nox = self.device.execute(Sen5xI2cCmdReadMeasuredRawValues())
    return (None if raw_voc == 0xFFFF else raw_voc,
            None if raw_nox == 0xFFFF else raw_nox)

  def publish_raw_gas_signals(self):
    # The VOC and NOx indices are relative to each sensor's own recent average,
    # so they can't say how much VOC is in the air.  The raw signals behind
    # them aren't re-centred, which is what an absolute estimate needs
    # (SimpleAQ-Frontend issue #374).  This is extra data: a failure here is
    # logged but doesn't mark the sensor as failed.
    if self.raw_signal_failures >= RAW_SIGNAL_MAX_FAILURES:
      return False

    result = False
    try:
      raw_voc, raw_nox = self.read_raw_gas_signals()
      self.raw_signal_failures = 0
    except Exception as err:
      self.raw_signal_failures += 1
      logging.warning("Could not read SEN5X raw VOC/NOx signals ({} of {}): {}".format(
          self.raw_signal_failures, RAW_SIGNAL_MAX_FAILURES, err))
      if self.raw_signal_failures >= RAW_SIGNAL_MAX_FAILURES:
        logging.warning("Giving up on SEN5X raw VOC/NOx signals until the next restart.")
      return False

    if raw_voc is not None:
      result = self._try_write('SEN5X', 'voc_raw_ticks', raw_voc) or result
    if raw_nox is not None:
      result = self._try_write('SEN5X', 'nox_raw_ticks', raw_nox) or result
    return result

  def publish(self):
    logging.info('Publishing SEN5X data')
    result = False
    try:
      data = self.read()

      if not self.has_transmitted_device_info:
        try:
          result = self._try_write('SEN5X', 'firmware_version', '{}.{}'.format(self.device.get_version().firmware.major, self.device.get_version().firmware.minor)) or result
        except Exception as err:
          self._try_write_error('SEN5X', 'firmware_version', str(err))
          raise err

        try:
          result = self._try_write('SEN5X', 'hardware_version', '{}.{}'.format(self.device.get_version().hardware.major, self.device.get_version().hardware.minor)) or result
        except Exception as err:
          self._try_write_error('SEN5X', 'hardware_version', str(err))
          raise err

        try:
          result = self._try_write('SEN5X', 'protocol_version', '{}.{}'.format(self.device.get_version().protocol.major, self.device.get_version().protocol.minor)) or result
        except Exception as err:
          self._try_write_error('SEN5X', 'protocol_version', str(err))
          raise err

        try:
          result = self._try_write('SEN5X', 'product_name', self.device.get_product_name()) or result
        except Exception as err:
          self._try_write_error('SEN5X', 'product_name', str(err))
          raise err

        try:
          result = self._try_write('SEN5X', 'serial_number', self.device.get_serial_number()) or result
        except Exception as err:
          self._try_write_error('SEN5X', 'serial_number', str(err))
          raise err

        self.has_transmitted_device_info = True

      if data:
        # NAN values are NOT valid JSON.  We will not send anything if a nan value is ever found for any reason.
        if not math.isnan(data.ambient_humidity.percent_rh):
          try:
            result = self._try_write('SEN5X', 'relative_humidity_pct', data.ambient_humidity.percent_rh) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'relative_humidity_pct', str(err))
            raise err
        if not math.isnan(data.ambient_temperature.degrees_celsius):
          try:
            result = self._try_write('SEN5X', 'temperature_C', data.ambient_temperature.degrees_celsius) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'temperature_C', str(err))
            raise err
        if not math.isnan(data.mass_concentration_10p0.physical):
          try:
            result = self._try_write('SEN5X', 'pm10.0_ug_m3', data.mass_concentration_10p0.physical) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'pm10.0_ug_m3', str(err))
            raise err
        if not math.isnan(data.mass_concentration_1p0.physical):
          try:
            result = self._try_write('SEN5X', 'pm1.0_ug_m3', data.mass_concentration_1p0.physical) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'pm1.0_ug_m3', str(err))
            raise err
        if not math.isnan(data.mass_concentration_2p5.physical):
          try:
            result = self._try_write('SEN5X', 'pm2.5_ug_m3', data.mass_concentration_2p5.physical) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'pm2.5_ug_m3', str(err))
            raise err
        if not math.isnan(data.mass_concentration_4p0.physical):
          try:
            result = self._try_write('SEN5X', 'pm4.0_ug_m3', data.mass_concentration_4p0.physical) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'pm4.0_ug_m3', str(err))
            raise err
        if not math.isnan(data.nox_index.scaled):
          try:
            result = self._try_write('SEN5X', 'nox_index', data.nox_index.scaled) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'nox_index', str(err))
            raise err
        if not math.isnan(data.voc_index.scaled):
          try:
            result = self._try_write('SEN5X', 'voc_index', data.voc_index.scaled) or result
          except Exception as err:
            self._try_write_error('SEN5X', 'voc_index', str(err))
            raise err

        result = self.publish_raw_gas_signals() or result
      else:
        logging.info("Data was not ready for SEN5X.")
    except Exception as err:
      logging.error("Error getting data from SEN5X.  Is this sensor correctly installed and the cable attached tightly:  " + str(err));
      result = self.name

    return result

  def __enter__(self):
    self.device.start_measurement()

  def __exit__(self, exception_type, exception_value, traceback):
    self.device.stop_measurement()
