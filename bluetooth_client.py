#!/usr/bin/env python3

import argparse
import asyncio
from bleak import BleakClient
from bleak import discover
import logging
import sys


async def find_simpleaq_device(prefix):
  nearby_devices = await discover() 

  for device in nearby_devices:
    logging.debug("Found device while scanning: '{}'".format(device))
    if device.name.lower().startswith(prefix.lower()):
      return device

  # For some reason, the device name sometimes isn't recognized
  # until we connect at least once.
  for device in nearby_devices:
    try:
      if device.name.lower().startswith(prefix.lower()):
        return device

      # For some reason, the device name sometimes isn't recognized
      # until we connect at least once.
      async with BleakClient(device, timeout=10) as client:
        logging.debug("Connected to device: '{}'".format(device))
#        svcs = await client.get_services()
    except Exception as err:
      logging.debug("Failed to connect to device {}: {}".format(device, str(err)))


async def main(args):
  # Configure logging.
  loglevels = {
      'critical': logging.CRITICAL,
      'error': logging.ERROR,
      'warning': logging.WARNING,
      'info': logging.INFO,
      'debug': logging.DEBUG
  }

  logging.basicConfig(stream=sys.stderr, level=loglevels[args.loglevel])

  # Let's search for the device.
  logging.info("Scanning for device prefixed with {}.  Press Ctrl+C to cancel.".format(args.name))
  device = None
  while not device:
    try:
      device = await find_simpleaq_device(args.name)
    except Exception as err:
      logging.info("Are you sure the device you're using supports bluetooth?")
      logging.info("If you're sure you have working bluetooth on Ubuntu, you could try: ")
      logging.info("sudo rfkill unblock bluetooth")
      logging.info("sudo systemctl restart bluetooth")
      logging.info("sudo systemctl status bluetooth")
      logging.error(str(err))
      return

  logging.info("Found SimpleAQ device: {}".format(device))

  # Ok, we found the device.

#      try:
#        async with BleakClient(device, timeout=30) as client:
#          svcs = await client.get_services()
#          print("Services:")
#          for service in svcs:
#            print(service)
#      except Exception as scan_err:
#        logging.error(str(scan_err))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth programmer for SimpleAQ device.")

  parser.add_argument('--name', help="The case-insensitive device name, or a prefix thereof, to look for.", default='simpleaq')
  parser.add_argument('--loglevel', help="Log level for device.", default='info', choices=['info', 'debug', 'warn', 'error', 'critical'])

  args = parser.parse_args()

  sys.exit(asyncio.run(main(args)))

