#!/usr/bin/env python3

# NOTE:  See https://wiki.debian.org/BluetoothUser
# Maybe the devices just need to be paired first.

import argparse
import asyncio
from bleak import BleakClient
from bleak import discover
from bless import GATTAttributePermissions
import logging
import sys

from bluetooth_constants import SIMPLEAQ_CHARACTERISTICS
from bluetooth_constants import SIMPLEAQ_SERVICE_UUID 


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
  while True:
    try:
      async with BleakClient(device, timeout=30) as client:
        # Ensure that the device we connected to is advertising the SimpleAQ service.
        svcs = await client.get_services()
        found_service = False
        for service in svcs:
          if service.uuid.lower() == SIMPLEAQ_SERVICE_UUID.lower():
            found_service = True

        if not found_service:
          logging.error("SimpleAQ service not found.  Found services follow:")
          for service in svcs:
            logging.error(str(service))

        # None of this will work if the device isn't paired or connected.
        await client.connect()

        # Connect to the service and dump all variables.
        for characteristic_uuid, values in SIMPLEAQ_CHARACTERISTICS.items():
          logging.debug("Attempting to read characteristic {}:".format(characteristic_uuid))
          result = await client.read_gatt_char(characteristic_uuid)
          if values.get('permissions') and values['permissions'] & GATTAttributePermissions.readable: 
            logging.info("{}: {}".format(values.get('name') or characteristic_uuid, result.encode('utf-8')))
          else:
            logging.info("{}: [write-only]".format(values.get('name')))

        # TODO:  Executed desired operations...
    except Exception as err:
      logging.error(str(err))
      logging.error("Retrying.  Press Ctrl+C to cancel.")


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth programmer for SimpleAQ device.")

  parser.add_argument('--name', help="The case-insensitive device name, or a prefix thereof, to look for.", default='simpleaq')
  parser.add_argument('--loglevel', help="Log level for device.", default='info', choices=['info', 'debug', 'warn', 'error', 'critical'])

  args = parser.parse_args()

  sys.exit(asyncio.run(main(args)))

