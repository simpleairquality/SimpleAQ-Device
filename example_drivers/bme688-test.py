#!/usr/bin/env python3

import board
import adafruit_bme680
i2c = board.I2C()
sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c)
print('Temperature: {} degrees C'.format(sensor.temperature))
print('Gas: {} ohms'.format(sensor.gas))
print('Humidity: {}%'.format(sensor.humidity))
print('Pressure: {}hPa'.format(sensor.pressure))
