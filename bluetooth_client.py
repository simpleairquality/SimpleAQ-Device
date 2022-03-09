#!/usr/bin/env python3

import argparse
import bluetooth
import logging
import sys


def find_simpleaq_device(port):
  try:
    nearby_devices = bluetooth.discover_devices(lookup_names=True) 
    print(nearby_devices)
  except Exception as err:
    logging.info("Are you sure the device you're using supports bluetooth?")
    logging.error(str(err))
    return 


def main(args):
  # Configure logging.
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  # Find the SimpleAQ device
  try:
    device = args.device or find_simpleaq_device(args.port)
  except Exception as err:
    logging.info("Are you sure the device you're using supports bluetooth?")
    logging.error(str(err))
    return 1 


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth listener for SimpleAQ device.")

  parser.add_argument('--port', type=int, help="Port to write to.", default=3)
  parser.add_argument('--device', help="Device MAC address to write to.  If not provided, we will try to auto-detect.")

  args = parser.parse_args()

  sys.exit(main(args))

