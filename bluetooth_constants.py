#!/usr/bin/env python3

from bless import (
        GATTCharacteristicProperties,
        GATTAttributePermissions
        )

SIMPLEAQ_SERVICE_UUID = "8EA64567-4E6E-4767-B1EF-C408A9299100"

SIMPLEAQ_CHARACTERISTICS = {
    "8EA64567-4E6E-4767-B1EF-C408A9299101": {
        'name': "influx_org",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299102": {
        'name': "influx_bucket",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299103": {
        'name': "influx_token",
        'characteristics': (
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299104": {
        'name': "influx_server",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299105": {
        'name': "simpleaq_interval",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299106": {
        'name': "datafile_prefix",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299107": {
        'name': "network.ssid",
        'characteristics': (
            GATTCharacteristicProperties.read |
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.readable |
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299108": {
        'name': "network.psk",
        'characteristics': (
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.writeable
            )
    },
    "8EA64567-4E6E-4767-B1EF-C408A9299109": {
        'name': "reboot",
        'characteristics': (
            GATTCharacteristicProperties.write |
            GATTCharacteristicProperties.indicate
            ),
        'permissions': (
            GATTAttributePermissions.writeable
            )
    },
}

