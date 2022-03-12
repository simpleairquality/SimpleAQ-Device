#!/usr/bin/env python3

import argparse
import asyncio
from bleak import BleakClient
from bleak import discover
import logging
import sys


async def find_simpleaq_device():
  try:
    nearby_devices = await discover() 

    for device in nearby_devices:
      print("Device:")
      print(device)
      try:
        async with BleakClient(device, timeout=30) as client:
          svcs = await client.get_services()
          print("Services:")
          for service in svcs:
            print(service)
      except Exception as scan_err:
        logging.error(str(scan_err))

  except Exception as err:
    logging.info("Are you sure the device you're using supports bluetooth?")
    logging.info("If you're sure you have working bluetooth on Ubuntu, you could try: ")
    logging.info("sudo rfkill unblock bluetooth")
    logging.info("sudo systemctl restart bluetooth")
    logging.info("sudo systemctl status bluetooth")
    logging.error(str(err))
    return 


async def main(args):
  # Configure logging.
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  # Find the SimpleAQ device
  try:
    device = await find_simpleaq_device()
  except Exception as err:
    logging.info("Are you sure the device you're using supports bluetooth?")
    logging.error(str(err))
    return 1 


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth listener for SimpleAQ device.")

  args = parser.parse_args()

  sys.exit(asyncio.run(main(args)))

