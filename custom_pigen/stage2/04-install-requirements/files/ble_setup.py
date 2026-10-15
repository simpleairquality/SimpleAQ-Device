#!/usr/bin/env python3
"""SimpleAQ BLE provisioning service.

Advertises a GATT service that the SimpleAQ app uses to hand the device its
WiFi credentials, device id and API token.  The protocol is documented in
README.md under "Using the SimpleAQ app over Bluetooth".

Design notes:

- The service only runs while the device is unprovisioned, meaning there is
  no real token in /etc/environment.  A provisioned device never advertises,
  regardless of whether it happens to be online at the moment the service
  starts.  The reset endpoint clears the token to bring provisioning back.
- Joining WiFi can take tens of seconds.  It runs on a worker thread so the
  GATT write that triggers it is acknowledged immediately.  BlueZ dispatches
  characteristic callbacks on the single GLib main loop, and blocking it
  there used to trip the phone's 30 second ATT timeout and drop the link.
- Progress is reported through the STATUS characteristic (read + notify).
- Credentials go into the "Wifi" NetworkManager profile that the rest of the
  image (hostap_config.py, wifi-watchdog.sh) already manages, instead of a
  new profile per SSID.
- After a successful join the token is persisted and the service keeps
  advertising until the app disconnects, plus a grace period, so the app can
  read the final status or reconnect to verify.
"""

import logging
import os
import subprocess
import sys
import threading
import time

import dbus
import dotenv
from bluezero import adapter
from bluezero import constants
from bluezero import peripheral
from gi.repository import GLib

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("simpleaq-ble")

ENV_FILE = "/etc/environment"
TOKEN_ENV_FILE = "/etc/simpleaq/device_token.env"
TOKEN_PLACEHOLDER = "YOUR_TOKEN_HERE"
BUCKET_PLACEHOLDER = "YOUR_BUCKET_HERE"

# Must match files/wifi.nmconnection; shared with hostap_config.py and
# wifi-watchdog.sh, which look the profile up by this name.
WIFI_CONNECTION = "Wifi"
WIFI_INTERFACE = "wlan0"
INTERNET_CHECK_HOST = "www.simpleaq.org"

LOCAL_NAME = "SimpleAQ_Setup"
SERVICE_UUID = "b4250400-fb4b-4746-b2b0-93f0e61122c6"
SSID_UUID = "b4250401-fb4b-4746-b2b0-93f0e61122c6"
PASS_UUID = "b4250402-fb4b-4746-b2b0-93f0e61122c6"
TOKEN_UUID = "b4250403-fb4b-4746-b2b0-93f0e61122c6"
DEVICE_ID_UUID = "b4250404-fb4b-4746-b2b0-93f0e61122c6"
STATUS_UUID = "b4250405-fb4b-4746-b2b0-93f0e61122c6"

# Values of the STATUS characteristic (ASCII strings).
STATUS_IDLE = "IDLE"                # waiting for SSID, password and token
STATUS_CONNECTING = "CONNECTING"    # WiFi join in progress
STATUS_CONNECTED = "CONNECTED"      # online and token saved; provisioning complete
STATUS_WIFI_FAILED = "WIFI_FAILED"  # could not join the network; re-send credentials
STATUS_NO_INTERNET = "NO_INTERNET"  # joined WiFi and saved the token, backend unreachable

ADAPTER_WAIT_SEC = 60           # how long to wait for hci0 to appear at boot
WIFI_CONNECT_TIMEOUT_SEC = 45
INTERNET_CHECK_WINDOW_SEC = 30  # DHCP and DNS can lag the association by a few seconds
SHUTDOWN_GRACE_SEC = 60         # keep advertising this long after the last client leaves


def to_text(value):
    return bytes(value).decode("utf-8", errors="replace")


def to_bytes(text):
    return list(text.encode("utf-8"))


def env_value(key):
    try:
        return (dotenv.dotenv_values(ENV_FILE).get(key) or "").strip()
    except Exception as e:
        log.error("Could not read %s: %s", ENV_FILE, e)
        return ""


def is_provisioned():
    token = env_value("influx_token")
    return bool(token) and token != TOKEN_PLACEHOLDER


def check_internet(timeout_sec=3):
    try:
        subprocess.run(["ping", "-c", "1", "-W", str(timeout_sec), INTERNET_CHECK_HOST],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True, timeout=timeout_sec + 5)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def wait_for_internet(window_sec):
    deadline = time.monotonic() + window_sec
    while True:
        if check_internet():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(3)


def read_device_id():
    bucket = env_value("influx_bucket")
    if bucket and bucket != BUCKET_PLACEHOLDER:
        return to_bytes(bucket)
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("Serial"):
                    return to_bytes(f"SimpleAQ_Pi_{line.split(':')[1].strip()}")
    except Exception:
        pass
    return to_bytes("SimpleAQ_Pi")


def write_device_id(value, options):
    device_id = to_text(value)
    log.info("Device id set to %r", device_id)
    try:
        dotenv.set_key(ENV_FILE, "influx_bucket", device_id)
    except Exception as e:
        log.error("Failed to update influx_bucket in %s: %s", ENV_FILE, e)


def persist_token(token):
    try:
        dotenv.set_key(ENV_FILE, "influx_token", token)
    except Exception as e:
        log.error("Failed to update influx_token in %s: %s", ENV_FILE, e)
    try:
        os.makedirs(os.path.dirname(TOKEN_ENV_FILE), exist_ok=True)
        with open(TOKEN_ENV_FILE, "w") as f:
            f.write(f"SIMPLEAQ_TOKEN={token}\n")
    except Exception as e:
        log.error("Failed to write %s: %s", TOKEN_ENV_FILE, e)


def nmcli(*args, timeout=60):
    return subprocess.run(["nmcli", *args], check=True, timeout=timeout,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def wifi_profile_exists():
    names = nmcli("-t", "-f", "NAME", "connection", "show").stdout.splitlines()
    return WIFI_CONNECTION in names


def configure_wifi_profile(ssid, password):
    """Point the shared "Wifi" profile at the given network.

    Uses the same settings as hostap_config.set_wifi_credentials so both
    provisioning paths produce an identical profile.
    """
    if not wifi_profile_exists():
        log.warning("NetworkManager profile %r is missing; recreating it", WIFI_CONNECTION)
        nmcli("connection", "add", "type", "wifi", "ifname", WIFI_INTERFACE,
              "con-name", WIFI_CONNECTION, "ssid", ssid)
    common = ["802-11-wireless.ssid", ssid,
              "802-11-wireless.band", "bg",
              "802-11-wireless.powersave", "2",
              "connection.autoconnect", "yes",
              "connection.autoconnect-retries", "0",
              "ipv4.dns-priority", "-100",
              "ipv4.route-metric", "100"]
    if password:
        nmcli("connection", "modify", WIFI_CONNECTION, *common,
              "802-11-wireless-security.key-mgmt", "wpa-psk",
              "802-11-wireless-security.psk", password,
              "802-11-wireless-security.psk-flags", "0")
    else:
        nmcli("connection", "modify", WIFI_CONNECTION, *common)
        nmcli("connection", "modify", WIFI_CONNECTION, "remove", "802-11-wireless-security")


def activate_wifi():
    # An explicit `up` also clears any manual-deactivation block left by a reset.
    nmcli("--wait", str(WIFI_CONNECT_TIMEOUT_SEC), "connection", "up", WIFI_CONNECTION,
          timeout=WIFI_CONNECT_TIMEOUT_SEC + 15)


def connected_client_count():
    """Ask BlueZ how many devices are connected, rather than trusting callback bookkeeping."""
    try:
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object(constants.BLUEZ_SERVICE_NAME, "/"),
                                 constants.DBUS_OM_IFACE)
        objects = manager.GetManagedObjects()
    except Exception as e:
        log.warning("Could not query connected clients: %s", e)
        return 0
    count = 0
    for interfaces in objects.values():
        device = interfaces.get(constants.DEVICE_INTERFACE)
        if device and bool(device.get("Connected", False)):
            count += 1
    return count


class Provisioner:
    def __init__(self):
        self.ssid = None
        self.password = None
        self.token = None
        self.status = STATUS_IDLE
        self.status_chrc = None
        self.peripheral = None
        self.worker = None
        self.complete = False
        self.shutdown_source = None

    # ---- GATT callbacks; BlueZ invokes these on the GLib main loop ----

    def write_ssid(self, value, options):
        self.ssid = to_text(value)
        log.info("Received SSID %r", self.ssid)
        self._maybe_start_join()

    def write_pass(self, value, options):
        self.password = to_text(value)
        log.info("Received WiFi password (%d characters)", len(self.password))
        self._maybe_start_join()

    def write_token(self, value, options):
        self.token = to_text(value)
        log.info("Received token (%d characters)", len(self.token))
        self._maybe_start_join()

    def read_status(self):
        return to_bytes(self.status)

    def on_status_notify(self, notifying, characteristic):
        # Push the current state to a new subscriber so it never has to poll.
        if notifying:
            characteristic.set_value(to_bytes(self.status))

    def _maybe_start_join(self):
        if not self.ssid or self.password is None or not self.token:
            return
        if self.worker is not None and self.worker.is_alive():
            log.info("WiFi join already in progress; ignoring repeated write")
            return
        # Allow re-provisioning within the same session.
        self.complete = False
        self._cancel_shutdown()
        self._set_status(STATUS_CONNECTING)
        self.worker = threading.Thread(target=self._join,
                                       args=(self.ssid, self.password, self.token),
                                       daemon=True)
        self.worker.start()

    # ---- worker thread; report back to the main loop through GLib.idle_add ----

    def _join(self, ssid, password, token):
        try:
            configure_wifi_profile(ssid, password)
            activate_wifi()
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or "").strip()
            log.error("WiFi join failed for %r: %s", ssid, detail)
            GLib.idle_add(self._set_status, STATUS_WIFI_FAILED)
            return
        except subprocess.TimeoutExpired:
            log.error("WiFi join timed out for %r", ssid)
            GLib.idle_add(self._set_status, STATUS_WIFI_FAILED)
            return
        except Exception:
            log.exception("Unexpected error while joining %r", ssid)
            GLib.idle_add(self._set_status, STATUS_WIFI_FAILED)
            return

        log.info("Joined WiFi network %r", ssid)
        persist_token(token)
        # Reload the token right away; the recorder tolerates being offline.
        subprocess.run(["systemctl", "restart", "simpleaq.service"], check=False)

        if wait_for_internet(INTERNET_CHECK_WINDOW_SEC):
            log.info("Backend reachable; provisioning complete")
            GLib.idle_add(self._finish, STATUS_CONNECTED)
        else:
            log.warning("Joined WiFi but %s is unreachable; token saved, uploads will "
                        "start once the network allows", INTERNET_CHECK_HOST)
            GLib.idle_add(self._set_status, STATUS_NO_INTERNET)

    # ---- main loop ----

    def _set_status(self, status):
        self.status = status
        log.info("Status -> %s", status)
        if self.status_chrc is not None:
            self.status_chrc.set_value(to_bytes(status))
        return False  # when called through idle_add: run once

    def _finish(self, status):
        self._set_status(status)
        self.complete = True
        self._reevaluate_shutdown()
        return False

    def on_connect(self, adapter_address, device_address=None):
        # bluezero calls this with (adapter, device) on PropertiesChanged and
        # with a single Device object on InterfacesAdded; we need neither.
        log.info("Client connected")
        self._reevaluate_shutdown()

    def on_disconnect(self, adapter_address, device_address):
        log.info("Client %s disconnected", device_address)
        self._reevaluate_shutdown()

    def _reevaluate_shutdown(self):
        if not self.complete:
            self._cancel_shutdown()
        elif connected_client_count() > 0:
            self._cancel_shutdown()
        else:
            self._schedule_shutdown()

    def _schedule_shutdown(self):
        if self.shutdown_source is None:
            log.info("Provisioning complete; stopping BLE in %d s unless a client reconnects",
                     SHUTDOWN_GRACE_SEC)
            self.shutdown_source = GLib.timeout_add_seconds(SHUTDOWN_GRACE_SEC, self._shutdown)

    def _cancel_shutdown(self):
        if self.shutdown_source is not None:
            GLib.source_remove(self.shutdown_source)
            self.shutdown_source = None

    def _shutdown(self):
        self.shutdown_source = None
        if connected_client_count() > 0:
            log.info("A client reconnected; staying up")
            return False
        log.info("Stopping BLE provisioning service")
        self.peripheral.mainloop.quit()
        return False


def wait_for_adapter():
    deadline = time.monotonic() + ADAPTER_WAIT_SEC
    while True:
        try:
            adapters = list(adapter.Adapter.available())
        except Exception as e:
            log.warning("Bluetooth adapter lookup failed: %s", e)
            adapters = []
        if adapters:
            return adapters[0]
        if time.monotonic() >= deadline:
            return None
        time.sleep(2)


def main():
    if is_provisioned():
        log.info("Device already has a token; not advertising. Use the reset endpoint to re-provision.")
        return 0

    dongle = wait_for_adapter()
    if dongle is None:
        log.error("No Bluetooth adapter found after %d s", ADAPTER_WAIT_SEC)
        return 1

    prov = Provisioner()
    ble = peripheral.Peripheral(dongle.address, local_name=LOCAL_NAME)
    prov.peripheral = ble

    ble.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)

    write_flags = ["write", "write-without-response"]
    ble.add_characteristic(srv_id=1, chr_id=1, uuid=SSID_UUID, value=[], notifying=False,
                           flags=write_flags, write_callback=prov.write_ssid)
    ble.add_characteristic(srv_id=1, chr_id=2, uuid=PASS_UUID, value=[], notifying=False,
                           flags=write_flags, write_callback=prov.write_pass)
    ble.add_characteristic(srv_id=1, chr_id=3, uuid=TOKEN_UUID, value=[], notifying=False,
                           flags=write_flags, write_callback=prov.write_token)
    ble.add_characteristic(srv_id=1, chr_id=4, uuid=DEVICE_ID_UUID, value=[], notifying=False,
                           flags=["read"] + write_flags,
                           read_callback=read_device_id, write_callback=write_device_id)
    ble.add_characteristic(srv_id=1, chr_id=5, uuid=STATUS_UUID, value=to_bytes(STATUS_IDLE),
                           notifying=False, flags=["read", "notify"],
                           read_callback=prov.read_status, notify_callback=prov.on_status_notify)
    prov.status_chrc = ble.characteristics[-1]

    ble.on_connect = prov.on_connect
    ble.on_disconnect = prov.on_disconnect

    log.info("Advertising %r on %s", LOCAL_NAME, dongle.address)
    ble.publish()  # runs the main loop until _shutdown() quits it

    try:
        ble.ad_manager.unregister_advertisement(ble.advert)
    except Exception:
        pass  # bluetoothd drops it anyway once this process exits
    return 0


if __name__ == "__main__":
    sys.exit(main())
