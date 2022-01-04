#!/usr/bin/env python3

import board
import busio
import adafruit_gps

i2c = board.I2C()

gps = adafruit_gps.GPS_GtopI2C(i2c)

# Turn on the basic GGA and RMC info (what you typically want)
gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
# Set update rate to once a second (1hz) which is what you typically want.
gps.send_command(b"PMTK220,1000")

def process(data):
  if not data:
    return
  data_string = "".join([chr(b) for b in data])
  print(data_string, end="")

process(gps.read(32))
gps.send_command(b"PMTK605")  # request firmware version
process(gps.read(32))
print()
