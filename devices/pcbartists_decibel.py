#!/usr/bin/env python3

from absl import logging
from sensirion_i2c_driver import I2cConnection

from . import Sensor


class PCBArtistsDecibel(Sensor):
    """
    Driver for the PCBArtists I²C decibel meter.
    """

    I2C_ADDRESS = 0x48
    DB_REGISTER = 0x0A

    def __init__(self, remotestorage, localstorage, timesource, i2c_transceiver, **kwargs):
        super().__init__(remotestorage, localstorage, timesource)

        self.i2c_transceiver = i2c_transceiver
        self.conn = I2cConnection(i2c_transceiver)
        self.name = "PCBArtistsDecibel"
        logging.info("Initialized PCBArtists Decibel Sensor at address 0x%02X", self.I2C_ADDRESS)

    def read(self):
        try:
            # Write register address first
            self.conn.write(self.I2C_ADDRESS, [self.DB_REGISTER])
            # Then read 1 byte
            data = self.conn.read(self.I2C_ADDRESS, 1)
            if data and len(data) == 1:
                return int(data[0])  # dB SPL
            return None
        except Exception as err:
            logging.error("Error reading PCBArtistsDecibel: %s", err)
            return None

    def publish(self):
        try:
            db_value = self.read()
            if db_value is not None:
                result = self._try_write('PCBArtistsDecibel', 'sound_level_dB', db_value)
                return result
            else:
                logging.info("No data read from PCBArtistsDecibel.")
                return False
        except Exception as err:
            logging.error("Error publishing Decibel data: %s", err)
            return self.name
