#!/usr/bin/env python3

from absl import logging

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
        self.name = "PCBArtistsDecibel"

        # Try a simple address probe first (no register read)
        if not self._probe_device():
            raise Exception(f"PCBArtistsDecibel not found at address 0x{self.I2C_ADDRESS:02X}")

        read_result = self.read()
        if read_result is None:
            raise Exception("Failed to read from PCBArtistsDecibel")

        logging.info("Initialized PCBArtists Decibel Sensor at address 0x%02X", self.I2C_ADDRESS)

    def _probe_device(self):
        """Attempt to detect device presence with minimal bus interaction"""
        try:
            # Try a zero-byte write - many I2C implementations support this for device detection
            status, error, _ = self.i2c_transceiver.transceive(
                self.I2C_ADDRESS, 
                bytes([]),  # Empty write
                0,  # No read
                read_delay=0, 
                timeout=1  # Short timeout for probe
            )
            return status and not error
        except:
            return False

    def read(self):
        try:
            # Write register address first
            # Then read 1 byte
            status, error, data = self.i2c_transceiver.transceive(self.I2C_ADDRESS, bytes([self.DB_REGISTER]), 1, read_delay=0, timeout=10)

            if data and len(data) == 1:
                return int(data[0])  # dB SPL

            logging.info(f"Status {status} from PCBArtistsDecibel.  Error: {error}, Data: {data}")
            return None
        except Exception as err:
            logging.error("Error reading PCBArtistsDecibel: {}".format(str(err)))
            return None

    def publish(self):
        try:
            db_value = self.read()
            if db_value is not None:
                result = self._try_write('PCBArtistsDecibel', 'sound_level_dB', db_value)
                return result
            else:
                return False
        except Exception as err:
            logging.error("Error publishing Decibel data: {}".format(str(err)))
            return self.name
