#!/usr/bin/env python3
"""
SimpleAQ Bluetooth Pairing Agent
Implements BlueZ org.bluez.Agent1 D-Bus interface.
Handles headless Just-Works pairing and automatic authorization without stdin/prompts.
"""

import sys
import logging
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AGENT_PATH = "/org/simpleaq/bt_agent"

class SimpleAQAgent(dbus.service.Object):
    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        logging.info("Agent released")

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        logging.info(f"AuthorizeService: device={device}, uuid={uuid} -> APPROVED")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        logging.info(f"RequestPinCode: device={device} -> Returning default 0000")
        return "0000"

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        logging.info(f"RequestPasskey: device={device} -> Returning 0")
        return dbus.UInt32(0)

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        logging.info(f"RequestConfirmation: device={device}, passkey={passkey} -> AUTO-ACCEPTED")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        logging.info(f"RequestAuthorization: device={device} -> AUTO-ACCEPTED")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        logging.info(f"DisplayPasskey: device={device}, passkey={passkey}, entered={entered}")

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        logging.info(f"DisplayPinCode: device={device}, pincode={pincode}")

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        logging.info("Agent Request Cancelled by BlueZ")

def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    agent = SimpleAQAgent(bus, AGENT_PATH)

    try:
        obj = bus.get_object("org.bluez", "/org/bluez")
        manager = dbus.Interface(obj, "org.bluez.AgentManager1")
        manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")
        manager.RequestDefaultAgent(AGENT_PATH)
        logging.info("SimpleAQ Bluetooth Agent registered successfully (NoInputNoOutput)")
    except Exception as e:
        logging.error(f"Failed to register D-Bus Agent: {e}")
        sys.exit(1)

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
