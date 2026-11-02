"""Raw VOC/NOx logging in devices/sen5x.py and devices/sen6x.py, tested
against a fake I2C bus that answers like a SEN55 (and a fake SEN66), so no
hardware is needed.

Run from the repository root:  python3 tests/test_raw_gas_signals.py
"""
import os
import struct
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_driver.transceiver_v1 import I2cTransceiverV1


def crc8(two):
  crc = 0xFF
  for b in two:
    crc ^= b
    for _ in range(8):
      crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
  return crc


def words(fmt, *vals, corrupt=False):
  raw = struct.pack('>' + fmt, *vals)
  out = b''
  for i in range(0, len(raw), 2):
    out += raw[i:i + 2] + bytes([crc8(raw[i:i + 2])])
  if corrupt:
    out = out[:-1] + bytes([out[-1] ^ 0xFF])
  return out


def text(s, n=48):
  data = s.encode().ljust(n * 2 // 3, b'\0')
  return words('H' * (len(data) // 2), *struct.unpack('>' + 'H' * (len(data) // 2), data))


class FakeSen55Bus(I2cTransceiverV1):
  def __init__(self):
    self.raw = (4500, 5000, 30123, 15432)   # 45 %RH, 25 °C, VOC ticks, NOx ticks
    self.raw_fails = False
    self.raw_corrupt = False
    self.calls = []

  @property
  def description(self):
    return 'fake SEN55'

  @property
  def channel_count(self):
    return None

  def transceive(self, slave_address, tx_data, rx_length, read_delay, timeout):
    cmd = struct.unpack('>H', bytes(tx_data[:2]))[0]
    self.calls.append(cmd)
    if cmd == 0xD100:   # version
      return self.STATUS_OK, None, words('BBBBBBBB', 2, 0, 0, 0, 1, 0, 0, 0)[:rx_length]
    if cmd in (0xD014, 0xD033):   # product name, serial number
      return self.STATUS_OK, None, text('SEN55' if cmd == 0xD014 else 'ABC123')
    if cmd == 0x0202:   # data ready
      return self.STATUS_OK, None, words('BB', 0, 1)
    if cmd == 0x03C4:   # measured values: PM x10, RH x100, T x200, VOC x10, NOx x10
      return self.STATUS_OK, None, words('HHHHhhhh', 52, 81, 95, 102, 4510, 5020, 1230, 10)
    if cmd == 0x03D2:   # raw values
      if self.raw_fails:
        return self.STATUS_NACK, None, None
      return self.STATUS_OK, None, words('hhHH', *self.raw, corrupt=self.raw_corrupt)
    if rx_length is None:   # reset, start, stop
      return self.STATUS_OK, None, b''
    raise AssertionError('unexpected command 0x%04X' % cmd)


class Storage:
  def __init__(self):
    self.rows = []

  def writejson(self, row):
    self.rows.append(row)


class Clock:
  def get_time(self):
    return '2026-11-02T20:00:00Z'


def fields(storage):
  return {r['field']: r.get('value') for r in storage.rows}


class Sen5xRawTest(unittest.TestCase):
  def make(self):
    from devices.sen5x import Sen5x
    self.bus = FakeSen55Bus()
    self.storage = Storage()
    sensor = Sen5x(remotestorage=None, localstorage=self.storage, timesource=Clock(), i2c_transceiver=self.bus)
    return sensor

  def test_publish_writes_raw_ticks_next_to_index(self):
    sensor = self.make()
    self.assertFalse(sensor.publish())
    f = fields(self.storage)
    self.assertEqual(f['voc_index'], 123.0)
    self.assertEqual(f['voc_raw_ticks'], 30123.0)
    self.assertEqual(f['nox_raw_ticks'], 15432.0)
    self.assertIsInstance(f['voc_raw_ticks'], float)   # stored as float like every other field
    self.assertEqual(self.bus.calls[-1], 0x03D2)        # read right after the measured values

  def test_unknown_nox_is_skipped(self):
    sensor = self.make()
    self.bus.raw = (4500, 5000, 30123, 0xFFFF)   # SEN54, or the first ~11 s after reset
    sensor.publish()
    f = fields(self.storage)
    self.assertIn('voc_raw_ticks', f)
    self.assertNotIn('nox_raw_ticks', f)

  def test_raw_failure_does_not_fail_sensor_and_gives_up_after_three(self):
    sensor = self.make()
    self.bus.raw_fails = True
    for _ in range(5):
      self.assertFalse(sensor.publish())   # PM, RH, T, indices still published, no sensor error
    f = fields(self.storage)
    self.assertIn('pm2.5_ug_m3', f)
    self.assertNotIn('voc_raw_ticks', f)
    self.assertEqual(self.bus.calls.count(0x03D2), 3)

  def test_bad_crc_counts_as_failure(self):
    sensor = self.make()
    self.bus.raw_corrupt = True
    sensor.publish()
    self.assertNotIn('voc_raw_ticks', fields(self.storage))
    self.assertEqual(sensor.raw_signal_failures, 1)
    self.bus.raw_corrupt = False
    sensor.publish()
    self.assertEqual(sensor.raw_signal_failures, 0)
    self.assertEqual(fields(self.storage)['voc_raw_ticks'], 30123.0)


class FakeSen66:
  def __init__(self):
    self.raw = {'raw_humidity': 45.0, 'raw_temperature': 25.0, 'raw_voc': 31000.0, 'raw_nox': 16000.0, 'raw_co2': 500.0}
    self.fail = False
    self.product_name = 'SEN66'
    self.serial_number = 'XYZ'
    self.version = (4, 0)
    self.data_ready = True
    self.device_status = types.SimpleNamespace(**{k: False for k in (
        'rht_sensor_error', 'fan_error', 'pm_sensor_error', 'gas_sensor_error', 'co2_sensor_2_error')})

  def reset(self):
    pass

  def all_measurements(self):
    return {'pm1_0': 5.0, 'pm2_5': 8.0, 'pm4_0': 9.0, 'pm10': 10.0, 'humidity': 45.0,
            'temperature': 25.0, 'voc_index': 120.0, 'nox_index': 1.0, 'co2': 500.0}

  def raw_values(self):
    if self.fail:
      raise OSError('I2C NACK')
    return dict(self.raw)


class Sen6xRawTest(unittest.TestCase):
  def make(self):
    sys.modules.setdefault('board', types.SimpleNamespace(I2C=lambda: None))
    fake = FakeSen66()
    sys.modules['adafruit_sen6x'] = types.SimpleNamespace(SEN66=lambda i2c: fake)
    sys.modules.pop('devices.sen6x', None)
    from devices.sen6x import Sen6x
    self.storage = Storage()
    sensor = Sen6x(remotestorage=None, localstorage=self.storage, timesource=Clock(), i2c_transceiver=None)
    return sensor, fake

  def test_publish_writes_raw_ticks(self):
    sensor, _ = self.make()
    self.assertFalse(sensor.publish())
    f = fields(self.storage)
    self.assertEqual(f['voc_raw_ticks'], 31000.0)
    self.assertEqual(f['nox_raw_ticks'], 16000.0)
    self.assertEqual(f['co2_ppm'], 500.0)

  def test_unknown_values_are_skipped(self):
    sensor, fake = self.make()
    fake.raw['raw_nox'] = None
    sensor.publish()
    self.assertNotIn('nox_raw_ticks', fields(self.storage))

  def test_failure_is_isolated(self):
    sensor, fake = self.make()
    fake.fail = True
    for _ in range(4):
      self.assertFalse(sensor.publish())
    f = fields(self.storage)
    self.assertIn('voc_index', f)
    self.assertNotIn('voc_raw_ticks', f)
    self.assertEqual(sensor.raw_signal_failures, 3)


if __name__ == '__main__':
  unittest.main(verbosity=2)
