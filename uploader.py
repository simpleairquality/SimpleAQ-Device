#!/usr/bin/env python3

import json
import os
import sys

from absl import app, flags, logging
import influxdb_client
import dotenv

dotenv.load_dotenv()
FLAGS = flags.FLAGS

def connect_to_influx():
  url = os.getenv('influx_server')
  token = os.getenv('influx_token')
  org = os.getenv('influx_org')
  return influxdb_client.InfluxDBClient(url=url, token=token, org=org)


def main(args):
  if len(args) != 1:
    sys.exit(f'Usage: {args[0]}')

  data_dir = os.getenv('data_directory')
  with connect_to_influx() as influx:
    files = os.listdir(data_dir)
    for logfile in files:
      with influx.write_api() as client:
        with open(os.path.join(data_dir, logfile)) as f:
          for line in f:
            record = json.loads(line)
            ts = int(1e9*record['timestamp'])
            logging.info(f'Uploading record: {record}')
            client.write(record['bucket'],
                         record['org'],
                         influxdb_client.Point(record['sensor'])
                           .field(record['field'], record['value'])
                           .time(ts))


if __name__ == '__main__':
  app.run(main)
