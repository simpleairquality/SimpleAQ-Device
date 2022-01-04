#!/usr/bin/env python3

import sys
import time

import board
import busio
from adafruit_pm25.i2c import PM25_I2C

i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
pm25 = PM25_I2C(i2c)

try:
  aqdata = pm25.read()
except RuntimeError as e:
  sys.exit(f"Unable to read from sensor: {e}")

print()
print("Concentration Units (standard)")
print("---------------------------------------")
print(
    "PM 1.0: %d\tPM2.5: %d\tPM10: %d"
    % (aqdata["pm10 standard"], aqdata["pm25 standard"], aqdata["pm100 standard"])
)
print("Concentration Units (environmental)")
print("---------------------------------------")
print(
    "PM 1.0: %d\tPM2.5: %d\tPM10: %d"
    % (aqdata["pm10 env"], aqdata["pm25 env"], aqdata["pm100 env"])
)
print("---------------------------------------")
print("Particles > 0.3um / 0.1L air:", aqdata["particles 03um"])
print("Particles > 0.5um / 0.1L air:", aqdata["particles 05um"])
print("Particles > 1.0um / 0.1L air:", aqdata["particles 10um"])
print("Particles > 2.5um / 0.1L air:", aqdata["particles 25um"])
print("Particles > 5.0um / 0.1L air:", aqdata["particles 50um"])
print("Particles > 10 um / 0.1L air:", aqdata["particles 100um"])
print("---------------------------------------")
