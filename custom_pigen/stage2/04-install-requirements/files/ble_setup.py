import subprocess
import time
import sys

# These variables will be populated by the BLE GATT Write Characteristics
received_ssid = None
received_password = None
received_token = None

def check_internet():
    """Returns True if the Pi can reach the SimpleAQ backend."""
    try:
        subprocess.check_call(
            ["ping", "-c", "1", "www.simpleaq.org"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False

def apply_wifi_credentials():
    """Uses Bookworm's NetworkManager (nmcli) to connect to WiFi."""
    global received_ssid, received_password
    
    if not received_ssid or not received_password:
        return False
        
    print(f"Attempting to connect to SSID: {received_ssid}")
    
    try:
        # Tell NetworkManager to connect to the new network
        subprocess.run([
            "nmcli", "dev", "wifi", "connect", 
            received_ssid, "password", received_password
        ], check=True)
        
        # Wait a moment for DHCP resolution
        time.sleep(5)
        
        if check_internet():
            print("Successfully connected to the internet!")
            save_simpleaq_token()
            
            # Shut down the BLE advertising to secure the device
            shutdown_ble_server()
            return True
        else:
            print("Connected to WiFi, but no internet access.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply WiFi credentials: {e}")
        return False

def save_simpleaq_token():
    """Saves the device token to the local storage environment for the main SimpleAQ app."""
    if received_token:
        with open("/etc/simpleaq/device_token.env", "w") as f:
            f.write(f"SIMPLEAQ_TOKEN={received_token}\n")

def shutdown_ble_server():
    """Gracefully kills this systemd service once setup is complete."""
    subprocess.run(["systemctl", "stop", "simpleaq-ble.service"])

# --- BLE GATT Server Boilerplate goes here ---
# 1. Register b4250400-fb4b-4746-b2b0-93f0e61122c6 as the primary service.
# 2. On write to b4250401..., update `received_ssid`.
# 3. On write to b4250402..., update `received_password`.
# 4. On write to b4250403..., update `received_token` and trigger `apply_wifi_credentials()`.
