# SimpleAQ Device Design Document

The SimpleAQ-Device firmware is designed to be extensible, robust and simple.
This document outlines how the SimpleAQ Device works.

# Sensor Hardware

A great sensor needs to be extensible.
We cannot assume that there is a "one-size fits all" solution for all environmental sensing needs.
Therefore, we have made extensibility to additional hardware a top design priority for our devices.

The SimpleAQ device is built on the [Raspberry Pi](https://www.raspberrypi.com/) platform, and in particularly we recommend a [Raspberry Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/) for the core of the device.
Attached to the Raspberry Pi will be a GPS unit and a suite of other optional sensors.

While the SimpleAQ firmware is designed primarily to support [I2C](https://en.wikipedia.org/wiki/I%C2%B2C) devices, we can theoretically support any device through the Raspberry Pi's [GPIO](https://en.wikipedia.org/wiki/General-purpose_input/output) pins.
At the time of this writing, we support:
-[Adafruit's GPS unit](../devices/gps.py)
-[Adafruit's PM25 unit](../devices/pm25.py)
-[Adafruit's BME688 unit](../devices/bme688.py)
-[Sensirion SEN54 and SEN55](../devices/sen5xply)

We welcome pull requests that add support for additional I2C devices, and will consider pull requests adding GPIO devices.
Devices are automatically detected by the [SimpleAQ service](../simpleaq.py), so no additional configuration is necessary beyond simply attaching the devices to the Raspberry Pi through I2C and inserting a MicroSD card with the firmware image on it.

# SimpleAQ Service

A great sensor needs to be robust.
In particular, our system is designed to tolerate several common points of failure:
-Data collection where internet is spotty.
-Uninterrupted data collection even if the SimpleAQ website or InfluxDB database goes down.
-Continued data collection even if a sensor fails.

The [SimpleAQ service](../simpleaq.py) is designed to support several different use cases:
-Data collection where no internet connection is possible.
-Data collection from a device that is not always in the same place.
-Data collection to the public [SimpleAQ website](https://www.simpleaq.org).
-Data collection to a private [InfluxDB database](https://www.influxdata.com/).

On booting, the SimpleAQ service first attempts to detect all supported devices present.
It will automatically start storing this data in a local [SQLite](https://www.sqlite.org) database.
If a backend such as the SimpleAQ website or InfluxDB database is configured, the service will attempt to connect to it and report current data as well as any stored backlog of data.
If a backend is not configured or fails to connect, it will start a local [hostapd](https://en.wikipedia.org/wiki/Hostapd) wifi network so that users can connect to correct the issue, configure one or download local data.
The service will periodically retry connecting to the configured backend in case the failure to connect was only temporary.

# Configuration

A great sensor needs to be simple.
A SimpleAQ device can be configured or debugged through its local [hostapd](https://en.wikipedia.org/wiki/Hostapd) wifi network using only a mobile phone.
When the user is connected to the configuration hostapd network, the user can configure by visiting either [http://simpleaq.setup](http://simpleaq.setup) or [http://192.168.4.1](http://192.168.4.1).
Upon clicking "Save Changes and Reboot", the settings will be applied and the entire system restarted.

The same configuration page also offers the opportunity to:
-Download stored local data
-Delete stored local data
-View several logs for debugging issues

# Custom Devices

Quality data leads to quality science, and quality science leads to action.
We believe that you can't have quality data or quality science without transparency.
In the spirit of transparency, the SimpleAQ device firmware is provided to you for free as an open-source project with an [MIT license](../LICENSE.md) so you can modify the firmware to suit your purposes with few restrictions.
We hope that you will submit your improvements to our firmware as pull requests so that we can help others in turn.
