import os

from absl import logging


class Sensor(object):
  def __init__(self, remotestorage, localstorage, timesource, log_errors=False, **kwargs):
    self.remotestorage = remotestorage
    self.localstorage = localstorage
    self.timesource = timesource
    self.log_errors = log_errors

  # Even though we never explicitly create rows, InfluxDB assigns a type
  # when a row is first written.  Apparently, sometimes intended float values are incorrectly
  # interpreted as a int and changing field types after the fact is hard.
  # So let's avoid that hassle entirely.
  def _make_ints_to_float(self, value):
    if isinstance(value, int):
      return float(value)
    return value

  def _try_log_error(self, point, field, error):
    if self.name == 'System':
      error_field = 'error'
    else:
      error_field = 'message'

    if self.log_errors:
      try:
        data_json = {
            'point': point,
            'field': field,
            error_field: str(error),
            'time': self.timesource.get_time()
        }

        self.localstorage.writejson(data_json);
      except Exception as backup_err:
        logging.error("Error saving data to local disk: " + str(backup_err))

  def _try_write(self, point, field, value):
    # Always save to disk first.
    try:
      data_json = {
          'point': point,
          'field': field,
          'value': self._make_ints_to_float(value),
          'time': self.timesource.get_time()
      }

      self.localstorage.writejson(data_json);

      return False
    except Exception as backup_err:
      # Something has truly gone sideways.  We can't even write backup data.
      logging.error("Error saving data to local disk: " + str(backup_err))
      return self.name

  def __enter__(self):
    pass

  def __exit__(self, exception_type, exception_value, traceback):
    pass
