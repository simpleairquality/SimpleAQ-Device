import subprocess
import time
import sys
import logging
from bluezero import peripheral
from bluezero import adapter

# Standardized UUIDs
SERVICE_UUID = 'b4250400-fb4b-4746-b2b0-93f0e61122c6'
SSID_UUID = 'b4250401-fb4b-4746-b2b0-93f0e61122c6'
PASS_UUID = 'b4250402-fb4b-4746-b2b0-93f0e61122c6'
TOKEN_UUID = 'b4250403-fb4b-4746-b2b0-93f0e61122c6'

received_ssid = ""
received_password = ""

def check_internet():
    """Check if the Pi can reach the SimpleAQ backend."""
    try:
        subprocess.check_call(["ping", "-c", "1", "www.simpleaq.org"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

# If already connected on boot, do not broadcast BLE.
if check_internet():
    sys.exit(0)

def apply_wifi_credentials():
    global received_ssid, received_password
    if not received_ssid or not received_password:
        return
        
    try:
        subprocess.run(["nmcli", "dev", "wifi", "connect", received_ssid, "password", received_password], check=True)
        time.sleep(5)
        
        if check_internet():
            # Gracefully terminate BLE advertising and systemd service
            subprocess.Popen(["systemctl", "stop", "simpleaq-ble.service"])
            sys.exit(0)
    except subprocess.CalledProcessError:
        pass

def write_ssid(value, options):
    global received_ssid
    received_ssid = bytes(value).decode('utf-8')

def write_pass(value, options):
    global received_password
    received_password = bytes(value).decode('utf-8')

def write_token(value, options):
    token = bytes(value).decode('utf-8')
    with open("/etc/simpleaq/device_token.env", "w") as f:
        f.write(f"SIMPLEAQ_TOKEN={token}\n")
    # Token is always sent last from the app, so we trigger WiFi connect here
    apply_wifi_credentials()

def main():
    adapters = list(adapter.Adapter.available())
    if not adapters:
        sys.exit(1)
        
    dongle = adapter.Adapter(adapters[0].address)
    ble_peripheral = peripheral.Peripheral(dongle.address, local_name='SimpleAQ_Setup', appearance=0)

    ble_peripheral.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)
    
    # SSID Characteristic
    ble_peripheral.add_characteristic(srv_id=1, chr_id=1, uuid=SSID_UUID, value=[], notifying=False, flags=['write'], read_callback=None, write_callback=write_ssid, notify_callback=None)
    
    # Password Characteristic
    ble_peripheral.add_characteristic(srv_id=1, chr_id=2, uuid=PASS_UUID, value=[], notifying=False, flags=['write'], read_callback=None, write_callback=write_pass, notify_callback=None)
    
    # Token Characteristic
    ble_peripheral.add_characteristic(srv_id=1, chr_id=3, uuid=TOKEN_UUID, value=[], notifying=False, flags=['write'], read_callback=None, write_callback=write_token, notify_callback=None)

    ble_peripheral.publish()

if __name__ == '__main__':
    main()
