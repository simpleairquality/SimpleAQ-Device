#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Code modified from:
# https://github.com/DFRobot/DFRobot_MultiGasSensor/blob/main/python/raspberrypi/DFRobot_MultiGasSensor.py

from absl import logging
from . import Sensor

import time
import smbus
import spidev
import os
import math
import RPi.GPIO as GPIO

I2C_MODE  = 0x01
tempSwitch = 0
temp = 0.0
SEND_WAIT = 0.5

def fuc_check_sum(i,ln):
  '''!
    @brief CRC check function
    @param i  CRC original data list
    @param ln Length
    @return CRC check value
  '''
  tempq=0
  for j in range(1,ln-1):
    tempq+=i[j]
  tempq=(((~tempq)&0xff)+1)
  return tempq

def clear_buffer(buf,length):
  '''!
    @brief List values are reset
    @param buf List to be cleared
    @param length Length
  '''
  for i in range(0,length):
    buf[i]=0


class DFRobot_GasType(object):
  '''!
    @brief Enumerates all known sensor types. DFRobot_MultiGasSensor.gastype
    @n     will be set to one of these.
  '''
  O2  = "O2"
  CO  = "CO"
  H2S = "H2S"
  NO2 = "NO2"
  O3  = "O3"
  CL2 = "CL2"
  NH3 = "NH3"
  H2  = "H2"
  HCL = "HCL"
  SO2 = "SO2"
  HF  = "HF"
  PH3 = "PH3"
  UNKNOWN = ""


class DFRobot_MultiGasSensor(object):
  '''!
    @brief This is a sensor parent class which can be used in complex environments to detect various gases.
    @details To detect gases like O2, CO, H2S, NO2, O3, CL2, NH3, H2, HCL, 
    @n       SO2, HF, PH3, which is achieved by just switching corresponding probes.
    @n       Meanwihle, it supports gas high/low threshold alarm.
    @n       Function
  '''  
  INITIATIVE =  0x03
  PASSIVITY  =  0x04
  O2         =  0x05
  CO         =  0x04
  H2S        =  0x03
  NO2        =  0x2C
  O3         =  0x2A
  CL2        =  0x31
  NH3        =  0x02
  H2         =  0x06
  HCL        =  0X2E
  SO2        =  0X2B
  HF         =  0x33
  PH3        =  0x45
  GASCON     =  0x00
  GASKIND    =  0x01
  ON         =  0x01
  OFF        =  0x00
  gasconcentration = 0.0 # Raw, uncorrected sensor measurement.
  gastype       =    ""
  gasunits      =    ""
  temp          =    0.0
  tempSwitch = OFF
  
  def __init__(self, bus):
    self.i2cbus = smbus.SMBus(bus)
    time.sleep(1)  # Avoids 121 IO Error
                   # See: https://stackoverflow.com/questions/52735862/getting-ioerror-errno-121-remote-i-o-error-with-smbus-on-python-raspberry-w
    self.__uart_i2c = I2C_MODE
        
  def __del__(self):
    if self.i2cbus:
      self.i2cbus.close()

  def __set_gastype(self, probe_type):
    '''!
      @brief   Sets instance gas type and units based on type read from sensor.
      @param probe_type Byte received from sensor indicating sensor type.
    '''
    if probe_type == self.O2:
      self.gastype = DFRobot_GasType.O2
      self.gasunits = "percent"
    elif probe_type == self.CO:
      self.gastype = DFRobot_GasType.CO
      self.gasunits = "ppm"
    elif probe_type == self.H2S:
      self.gastype = DFRobot_GasType.H2S
    elif probe_type == self.NO2:
      self.gasunits = "ppm"
      self.gastype = DFRobot_GasType.NO2
    elif probe_type == self.O3:
      self.gasunits = "ppm"
      self.gastype = DFRobot_GasType.O3
    elif probe_type == self.CL2:
      self.gasunits = "ppm"
      self.gastype = DFRobot_GasType.CL2
    elif probe_type == self.NH3:
      self.gasunits = "ppm"
      self.gastype = DFRobot_GasType.NH3
    elif probe_type == self.H2:
      self.gastype = DFRobot_GasType.H2
      self.gasunits = "ppm"
    elif probe_type == self.HCL:
      self.gastype = DFRobot_GasType.HCL
      self.gasunits = "ppm"
    elif probe_type == self.SO2:
      self.gastype = DFRobot_GasType.SO2
      self.gasunits = "ppm"
    elif probe_type == self.HF:
      self.gastype = DFRobot_GasType.HF
      self.gasunits = "ppm"
    elif probe_type == self.PH3:
      self.gastype = DFRobot_GasType.PH3
      self.gasunits = "ppm"
    else:
      self.gastype = DFRobot_GasType.UNKNOWN
      self.gasunits = ""


  def __adc_to_temp(self, temp_ADC):
    '''!
      @brief Converts temperature ADC measurement to temperature.
      @param temp_ADC 10-bit A/D measurement from onboard temperature sensor.
    '''
    Vpd3=float(temp_ADC/1024.0)*3
    Rth = Vpd3*10000/(3-Vpd3)

    if Rth <= 0:
      return 1/(1/(273.15+25))-273.15
    else:
      return 1/(1/(273.15+25)+1/3380.13*(math.log(Rth/10000)))-273.15


  def __temp_correction(self, Con):
    '''!
      @brief Performs temperature correction of sensor value.
      @param Con Measured value from sensor.
    '''

    # NOTE: this implementation replicates the thresholds and corrections
    # from the C++ version of the library as of commit 54e465b. The python
    # version was significantly different in many ways, resulting in different
    # results based on which library is used.

    # TODO: restructure all of the checks below to stop repeatedly checking
    # against the same tresholds over and over. This would be more efficient
    # and way more readable if all of the checks followed the pattern:
    #
    # if self.temp < threshold_1:
    #   Con = 0.0
    # elif self.temp < threshold_2:
    #   Con = some sort of correction
    # elif self.temp < theshold_3:
    #   Con = another correction
    # else:
    #   Con = 0.0
    
    # If temperature corrections not enabled, don't alter the sensor value.
    if self.tempSwitch != self.ON:
      return Con

    if self.gastype == DFRobot_GasType.O2:
      # No temperature dependency.
      pass

    elif self.gastype == DFRobot_GasType.CO:
      if (self.temp > -40) and (self.temp <= 20):
        Con = Con / (0.005 * self.temp + 0.9)
      elif (self.temp > 20) and (self.temp <= 40):
        Con = Con / (0.005 * self.temp + 0.9) - (0.3 *self.temp - 6)
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.H2S:
      if (self.temp > -20) and (self.temp <= 20):
        Con = Con / (0.006 * self.temp + 0.92)
      elif (self.temp > 20) and (self.temp < 40):
        Con = (Con / (0.006 * (self.temp) + 0.92) - (0.015 * (self.temp) + 2.4))
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range. (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.NO2:
      if (self.temp > -20) and (self.temp <= 0):
        Con = ((Con / (0.005 * (self.temp) + 0.9) - (-0.0025 * (self.temp))))
      elif (self.temp > 0) and (self.temp <= 20):
        Con = ((Con / (0.005 * (self.temp) + 0.9) - (0.005 * (self.temp) + 0.005)))
      elif (self.temp > 20) and (self.temp <= 40):
        Con = ((Con / (0.005 * (self.temp) + 0.9) - (0.0025 * (self.temp) + 0.1)));
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.O3:
      if (self.temp > -20) and (self.temp <= 0):
        Con = ((Con / (0.015 * (self.temp) + 1.1) - 0.05));
      elif (self.temp > 0) and (self.temp <= 20):
        Con = ((Con / 1.1 - (0.01 * (self.temp))));
      elif (self.temp > 20) and (self.temp <= 40):
        Con = ((Con / 1.1 - (-0.05 * (self.temp) + 0.3)));
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.CL2:
      if (self.temp > -20) and (self.temp < 0):
        Con = ((Con / (0.015 * (self.temp) + 1.1) - (-0.0025 * (self.temp))));
      elif (self.temp > 0) and (self.temp <= 20):
        Con = ((Con / 1.1 - 0.005 * (self.temp)));
      elif (self.temp > 20) and (self.temp < 40):
        Con = ((Con / 1.1 - (0.06 * (self.temp)-0.12)));
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.NH3:
      if (self.temp > -20) and (self.temp <= 0):
        Con = (Con / (0.08 * (self.temp) + 3.98) - (-0.005 * (self.temp) + 0.3));
      elif (self.temp > 0) and (self.temp <= 20):
        Con = (Con / (0.08 * (self.temp) + 3.98) - (-0.005 * (self.temp) + 0.3));
      elif (self.temp > 20) and (self.temp < 40):
        Con = (Con / (0.004 * (self.temp) + 1.08) - (-0.1 * (self.temp) + 2));
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.H2:
      if (self.temp > -20) and (self.temp < 40):
        Con = (Con / (0.74 * (self.temp) + 0.007) - 5);
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.HCL:
      # Apparently no correction is needed:  https://github.com/DFRobot/DFRobot_MultiGasSensor/blob/main/DFRobot_MultiGasSensor.cpp
      # But, this guy thinks so:  https://github.com/DFRobot/DFRobot_MultiGasSensor/pull/6/files#diff-0adb2c96bd2f192e2f369fdc6bf5e96c07a5db7775fb7e010f7e85e33b4bfb62
      pass
    elif self.gastype == DFRobot_GasType.SO2:
      # Apparently no correction is needed:  https://github.com/DFRobot/DFRobot_MultiGasSensor/blob/main/DFRobot_MultiGasSensor.cpp
      # But, this guy thinks so:  https://github.com/DFRobot/DFRobot_MultiGasSensor/pull/6/files#diff-0adb2c96bd2f192e2f369fdc6bf5e96c07a5db7775fb7e010f7e85e33b4bfb62
      pass
    elif self.gastype == DFRobot_GasType.HF:
      if (self.temp > -20) and (self.temp <= 0):
        Con = (((Con / 1) - (-0.0025 * (self.temp))));
      elif (self.temp > 0) and (self.temp <= 20):
        Con = Con/1 + 0.1
      elif (self.temp>20) and (self.temp < 40):
        Con = ((Con / 1 - (0.0375 * (self.temp)-0.85)));
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    elif self.gastype == DFRobot_GasType.PH3:
      if (self.temp > -20) and (self.temp < 40):
        Con = Con / (0.005 * self.temp + 0.9)
      else:
        logging.info("DFRobot MultiGas {} out of nominal operating temperature range (currently {}C).".format(self.gastype, self.temp))
        Con = None

    else: # Do not modify values for unknown sensors.
      pass

    # No sensor measurements are ever below zero, so it makes little sense
    # for the corrected version to be so.
    if Con and Con < 0:
      return 0.0

    return Con


  def analysis_all_data(self,recv):
    '''!
      @brief   The obtained data list by parsing.
      @param recv The obtained data
    '''    
    #recv[5]Indicate resolution, 0 indicate resolution is 1, 1 indicate resolution is 0.1, 2 indicate resolution is 0.01
    if(recv[5]==0):
      self.gasconcentration = (recv[2] << 8) + recv[3]
    elif(recv[5]==1):
      self.gasconcentration = 0.1*((recv[2] << 8) + recv[3])
    elif(recv[5]==2):
      self.gasconcentration = 0.01*((recv[2] << 8) + recv[3])

    # Update sensor type from info in response (byte 4).
    self.__set_gastype(recv[4])

    # Update current temperature.
    temp_ADC=(recv[6]<<8)+recv[7]
    self.temp = self.__adc_to_temp(temp_ADC)

    # Perform temperature correction of the value if enabled.
    Con = self.__temp_correction(self.gasconcentration)

    
  def change_acquire_mode(self,mode):
    '''!
      @brief Change the mode of reporting data to the main controller after the sensor has collected the gas.
      @param mode Mode select
      @n     INITIATIVE The sensor proactively reports data
      @n     PASSIVITY The sensor can report data only after the main controller sends request to it.
      @return Return whether the change of gas mode succeed
      @retval True   change success
      @retval False  change fail
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x78
    sendbuf[3]=mode
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if(recvbuf[2]==1):
      return True
    else:
      return False

  def read_gas_concentration(self):
    '''!
      @brief Get the gas concentration or type obtained by the sensor
      @return if data is transmitted normally, return gas concentration; otherwise, return 0xffff
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x86
    sendbuf[3]=0x00
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if(fuc_check_sum(recvbuf,8) == recvbuf[8]):
      self.gasconcentration = ((recvbuf[2]<<8)+recvbuf[3])*1.0

      # Scale measurement based on the number of decimal places indicated
      # by the sensor.
      decimal_digits = recvbuf[5]
      if decimal_digits == 1:
        self.gasconcentration = self.gasconcentration * 0.1
      elif decimal_digits == 2:
        self.gasconcentration = self.gasconcentration * 0.01

    else: # Checksum failed.
      logging.error("Checksum failed on DFRobot sensor {}".format(self.gastype))
      self.gasconcentration = None

    # Update sensor type from info in response (byte 4).
    self.__set_gastype(recvbuf[4])

    # Update temperature measurement if temperature correction is enabled.
    if(self.tempSwitch == self.ON):
      self.temp = self.read_temp()

    # Perform temperature correction of the value if enabled.
    self.uncorrectedgasconcentration = self.gasconcentration
    if self.gasconcentration is not None:
      self.gasconcentration = self.__temp_correction(self.gasconcentration)

    return self.uncorrectedgasconcentration, self.gasconcentration

  def read_gas_type(self):
    '''!
      @brief Get the gas type obtained by the sensor
      @return Gas type
      @n  O2   0x05
      @n  CO   0x04
      @n  H2S  0x03
      @n  NO2  0x2C
      @n  O3   0x2A
      @n  CL2  0x31
      @n  NH3  0x02
      @n  H2   0x06
      @n  HCL  0X2E
      @n  SO2  0X2B
      @n  HF   0x33
      @n  PH3  0x45
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x86
    sendbuf[3]=0x00
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if(fuc_check_sum(recvbuf,8) == recvbuf[8]):
      return (recvbuf[4])
    else:
      return 0xff   
    
  def set_threshold_alarm(self,switchof,threshold,gasType):
    '''!
      @brief Set sensor alarm threshold
      @param switchof Set whether to turn on alarm function
      @n        ON    Turn on alarm function
      @n        OFF   Turn off alarm function
      @param threshold Set alarm threshold
      @param gasType Gas type
      @return Whether setting threshold alarm succeed
      @retval True   change success
      @retval False  change fail
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    if self.gastype == DFRobot_GasType.O2:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.NO2:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.O3:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.CL2:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.HCL:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.SO2:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.HF:
      threshold *= 10
    elif self.gastype == DFRobot_GasType.PH3:
      threshold *= 10
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x89
    sendbuf[3]=switchof
    sendbuf[4]=threshold>>8
    sendbuf[5]=threshold
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if (recvbuf[8]!=fuc_check_sum(recvbuf,8)):
      return False
    if(recvbuf[2]==1):
      return True
    else:
      return False   

  def read_temp(self):
    '''!
      @brief Get sensor onboard temperature
      @return Board temperature, unit °C
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x87
    sendbuf[3]=0x00
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    temp_ADC=(recvbuf[2]<<8)+recvbuf[3]
    return self.__adc_to_temp(temp_ADC)
    
  def set_temp_compensation(self,tempswitch):
    '''!
      @brief Set whether to turn on temperature compensation, values output by sensor under different temperatures are various.
      @n     To get more accurate gas concentration, temperature compensation are necessary when calculating gas concentration.
      @param tempswitch Temperature compensation switch
                   ON  Turn on temperature compensation
                   OFF Turn off temperature compensation
    '''  
    self.tempSwitch = tempswitch
    
  def read_volatage_data(self):
    '''!
      @brief Get sensor gas concentration output by original voltage, which is different from reading sensor register directly.
      @n     The function is mainly for detecting whether the read gas concentration is right.
      @param  vopin Pin for receiving the original voltage output from sensor probe
      @return The original voltage output of sensor gas concentration
    '''
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x91
    sendbuf[3]=0x00
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if (recvbuf[8] != fuc_check_sum(recvbuf, 8)):
      return 0.0
    else:
      return (((recvbuf[2] << 8) + recvbuf[3])*3.0/1024*2)

  def change_i2c_addr_group(self,group):
    '''!
      @brief Change I2C address group
      @param  group The group number that the sensor is supposed to be
    '''   
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x92
    sendbuf[3]=group
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    if (recvbuf[8] != fuc_check_sum(recvbuf, 8)):
      return False
    else:
      return recvbuf[2]    
      

class DFRobot_MultiGasSensor_I2C(DFRobot_MultiGasSensor):
  def __init__(self ,bus ,addr):
    self.__addr = addr
    super(DFRobot_MultiGasSensor_I2C, self).__init__(bus)

  def data_is_available(self):
    '''
      * @brief Call this function in I2C active mode to determine the presence of data on data line
      * @return Whether data from sensor is available
      * @retval True  success is Available
      * @retval False  error is unavailable
      *
    ''' 
    sendbuf = [0] * 9
    recvbuf = [0] * 9
    clear_buffer(recvbuf,9)
    sendbuf[0]=0xff
    sendbuf[1]=0x01
    sendbuf[2]=0x88
    sendbuf[3]=0x00
    sendbuf[4]=0x00
    sendbuf[5]=0x00
    sendbuf[6]=0x00
    sendbuf[7]=0x00
    sendbuf[8]=fuc_check_sum(sendbuf,8)
    self.write_data(0,sendbuf,9)
    time.sleep(SEND_WAIT)
    recvbuf = self.read_data(0, 9)
    for i in range(0,8):
      print("%#x"%recvbuf[i])
    if (recvbuf[8] == fuc_check_sum(recvbuf, 8)):
      self.analysis_all_data(recvbuf)
      return True
    else:
      return False

  def write_data(self, reg, data , length):
    '''
      @brief writes data to a register
      @param reg register address
      @param value written data
    '''  
    try:
      self.i2cbus.write_i2c_block_data(self.__addr ,reg ,data)
      return
    except:
      logging.error("Failed to write data to DFRobot MultiGas Sensor on {}: {}".format(self.__addr, str(err))) 
      return

  def read_data(self, reg, length):
    '''
      @brief read the data from the register
      @param reg register address
      @param value read data
    '''
    recvbuf = [0] * 9
    try:
      rslt = self.i2cbus.read_i2c_block_data(self.__addr ,reg , length)
    except Exception as err:
      logging.error("Failed to read data from DFRobot MultiGas Sensor on {}: {}".format(self.__addr, str(err)))
      rslt = 0
      raise err
    recvbuf=rslt
    return recvbuf


class DFRobotMultiGas(Sensor):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    super().__init__(remotestorage, localstorage, timesource)

    # An additional kwarg, 'address', should be provided.
    # Each gas sensor on the bus must use a different DIP setting.
    #             | A0 | A1 |
    #             | 0  | 0  |    0x74
    #             | 0  | 1  |    0x75
    #             | 1  | 0  |    0x76
    #             | 1  | 1  |    0x77   default i2c address  
    # So, we need to try each of 0x74, 0x75, 0x76 and 0x77.

    self.sensor = DFRobot_MultiGasSensor_I2C(
        0x01,  # I2C_1.  TODO:  Support changing to another I2C bus?
        kwargs['address'])
    
    self.address = kwargs['address']
    max_wait_time_sec = 10
    time_waited = 0

    # This is how we'll detect whether the device is present and functional.
    change_success = False
    while not change_success and time_waited < max_wait_time_sec:
      try:
        change_success = self.sensor.change_acquire_mode(self.sensor.PASSIVITY)
      except OSError as err:
        # Retry OSError 121.
        logging.info("Error trying to change acquire mode for multi-gas sensor on {}: {}".format(kwargs['address'], str(err)))
      time_waited += 1
      time.sleep(1)

    if time_waited == max_wait_time_sec:
      raise Exception("Timed out waiting for multi-gas sensor on {}".format(kwargs['address']))

    self.sensor.set_temp_compensation(self.sensor.ON)

  def publish(self):
    logging.info('Publishing DFRobot Multi-Gas on I2C {} to remote.'.format(self.address))
    result = False
    try:
      uncorrected_gas_concentration, gas_concentration = self.sensor.read_gas_concentration()
      if self.sensor.gastype and self.sensor.gasunits:
        if uncorrected_gas_concentration is not None:
          result = self._try_write_to_remote('DFRobotMultiGas{}'.format(self.sensor.gastype), '{}_uncorrected_concentration_{}'.format(self.sensor.gastype, self.sensor.gasunits), uncorrected_gas_concentration) or result
        else:
          logging.warning("DFRobot Multi Gas {} failed to get uncorrected gas concentration!".format(self.sensor.gastype))

        if gas_concentration is not None:
          result = self._try_write_to_remote('DFRobotMultiGas{}'.format(self.sensor.gastype), '{}_concentration_{}'.format(self.sensor.gastype, self.sensor.gasunits), gas_concentration) or result
        else:
          logging.warning("DFRobot Multi Gas {} failed to get gas concentration!".format(self.sensor.gastype))

        result = self._try_write_to_remote('DFRobotMultiGas{}'.format(self.sensor.gastype), 'temperature_C', self.sensor.temp) or result
      else:
        logging.error("Unable to determine gas type or units on DFRobotMultiGas{} sensor on {}".format(self.dip, self.address))
        result = True
    except Exception as err:
      logging.error("Error getting data from DFRobotMultiGas{}.  Is this sensor correctly installed and the cable attached tightly: {}".format(self.dip, str(err)));
      result = True
    return result

class DFRobotMultiGas00(DFRobotMultiGas):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    self.dip = "00"
    super().__init__(remotestorage, localstorage, timesource, address=0x74)

class DFRobotMultiGas01(DFRobotMultiGas):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    self.dip = "01"
    super().__init__(remotestorage, localstorage, timesource, address=0x75)

class DFRobotMultiGas10(DFRobotMultiGas):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    self.dip = "10"
    super().__init__(remotestorage, localstorage, timesource, address=0x76)

class DFRobotMultiGas11(DFRobotMultiGas):
  def __init__(self, remotestorage, localstorage, timesource, **kwargs):
    self.dip = "11"
    super().__init__(remotestorage, localstorage, timesource, address=0x77)
