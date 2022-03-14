#!/usr/bin/env python3

import argparse
from configparser import ConfigParser
import logging
import asyncio
import dotenv
import sys
import threading
import os

from typing import Any

from bless import (
        BlessServer,
        BlessGATTCharacteristic,
        GATTCharacteristicProperties,
        GATTAttributePermissions
        )

from bluetooth_constants import SIMPLEAQ_SERVICE_UUID
from bluetooth_constants import SIMPLEAQ_CHARACTERISTICS

from wpasupplicantconf import WpaSupplicantConf


logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(name=__name__)
trigger: threading.Event = threading.Event()


def read_request(
        characteristic: BlessGATTCharacteristic,
        **kwargs
        ) -> bytearray:
    logger.debug(f"Reading {characteristic.value}")
    return characteristic.value


def write_request(
        characteristic: BlessGATTCharacteristic,
        value: Any,
        **kwargs
        ):
    # TODO:  Set the characteristic, and also update the appropriate config file.
    characteristic.value = value
    logger.debug(f"Char value set to {characteristic.value}")
    if characteristic.value == b'\x0f':
        logger.debug("NICE")
        trigger.set()

#  Initialize values for the Bluetooth characteristcs.
def getInitialValueForCharacteristic(characteristic_uuid, wpa_supplicant_file):
    # TODO:  Would it be better to get these values from the config files
    # themselves?
    if SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'influx_org':
      logger.info("Found influx_org: {}".format(os.getenv('influx_org')))
      return bytes(os.getenv('influx_org'), 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'influx_bucket':
      logger.info("Found influx_bucket: {}".format(os.getenv('influx_bucket')))
      return bytes(os.getenv('influx_bucket'), 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'influx_token':
      return None # Write-only
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'influx_server':
      logger.info("Found influx_server: {}".format(os.getenv('influx_server')))
      return bytes(os.getenv('influx_server'), 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'simpleaq_interval':
      logger.info("Found simpleaq_interval: {}".format(os.getenv('simpleaq_interval')))
      return bytes(os.getenv('simpleaq_interval'), 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'datafile_prefix':
      logger.info("Found datafile_prefix: {}".format(os.getenv('datafile_prefix')))
      return bytes(os.getenv('datafile_prefix'), 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'network.ssid':
      with open(wpa_supplicant_file) as wpa_supplicant:
        wpaconfig = WpaSupplicantConf(wpa_supplicant.read().split('\n'))
        if len(wpaconfig.networks()) > 1:
          logger.warning("Cannot edit WPA supplicant file:  {} networks.".format(len(wpaconfig.networks())))
          return None
        if len(wpaconfig.networks()) == 0:
          logger.info("No network currently configured.  No problem, we will create it if requested.")
          return None
        network = wpaconfig.networks().popitem(last=False)
        logger.info("Found ssid: {}".format(network[0]))
        return bytes(network[0], 'utf-8')
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name')  == 'network.psk':
      return None  # Write-only
    elif SIMPLEAQ_CHARACTERISTICS[characteristic_uuid].get('name') == 'reboot':
      return None  # Write-only

    logger.error("Unable to initialize characteristic: {}".format(characteristic_uuid))


async def run(loop, args):
    trigger.clear()
    # Instantiate the server
    my_service_name = "SimpleAQ Service"
    server = BlessServer(name=my_service_name, loop=loop)
    server.read_request_func = read_request
    server.write_request_func = write_request

    # Add Service
    await server.add_new_service(SIMPLEAQ_SERVICE_UUID)

    # Add Characteristics
    for characteristic_uuid, values in SIMPLEAQ_CHARACTERISTICS.items():
      await server.add_new_characteristic(
          SIMPLEAQ_SERVICE_UUID,
          characteristic_uuid,
          values['characteristics'],
          getInitialValueForCharacteristic(characteristic_uuid, args.wpa_supplicant_conf_file),
          values['permissions'])

    await server.start()
    logger.debug("Advertising")
    trigger.wait()
    await asyncio.sleep(2)
    # TODO:  I don't fully understand what the next few lines are doing.
    logger.debug("Updating")
    server.get_characteristic(my_char_uuid)
    server.update_value(
            simpleaq_service_uuid, "51FF12BB-3ED8-46E5-B4F9-D64E2FEC021B"
            )
    await asyncio.sleep(5)
    await server.stop()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth listener for SimpleAQ device.")

  parser.add_argument('--wpa-supplicant-conf-file', help="Location of the wpa_supplicant.conf file.", default="/etc/wpa_supplicant/wpa_supplicant.conf")
  parser.add_argument('--environment-file', help="Location of the system environment variables file.", default="/etc/environment")

  args = parser.parse_args()

  dotenv.load_dotenv(args.environment_file)

  loop = asyncio.get_event_loop()
  sys.exit(loop.run_until_complete(run(loop, args)))

