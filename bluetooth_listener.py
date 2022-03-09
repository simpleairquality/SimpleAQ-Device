#!/usr/bin/env python3

import argparse
import bluetooth
import logging
import sys

def main(args):
  # Configure logging.
  logging.basicConfig(stream=sys.stderr, level=logging.INFO)

  # First, we need to know where to listen.
  bluetooth_devices = bluetooth.bluez.read_local_bdaddr()

  # If there is no bluetooth device, fail.
  if not bluetooth_devices:
    logging.error("Cannot find a bluetooth device.")
    return 1

  # If there are mutliple local bluetooth addresses, then any must be equally good.
  bluetooth_device = bluetooth_devices[0]
  logging.info("Using bluetooth adapter at {}".format(bluetooth_device))

  while True:
    # Warning:  The documentation for BluetoothSocket is embarrassing.
    # https://pybluez.readthedocs.io/en/latest/api/bluetooth_socket.html
    # If we were kind, we would contribute documentation.
    socket = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    socket.bind((bluetooth_device, args.port))
    socket.listen(args.backlog)

    try:
      client, clientInfo = socket.accept()
      while True:
        data = client.recv(args.size)
        if data:
          logging.info("Received \"{}\" from bluetooth client.".format(data))
   
          # TODO:  Accept commands to set wifi options and environment variables.
          # TODO:  When we receive a "commit" command, we will update the variables and reboot.

          client.send("OK")
    except Exception as err:
      # If something went wrong, we won't do anythingand will go back to listening.
      logging.error(str(err))
      client.close()
      socket.close()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Bluetooth listener for SimpleAQ device.")

  parser.add_argument('--port', type=int, help="Port to listen on.", default=3)
  parser.add_argument('--backlog', type=int, help="Undocumented backlog argument in bluetooth library.", default=1)
  parser.add_argument('--size', type=int, help="Data packet max size.", default=1024)

  args = parser.parse_args()

  sys.exit(main(args))
