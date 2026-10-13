from flask import Flask, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/reset', methods=['POST', 'GET'])
def reset_device():
    # 1. Delete all saved NetworkManager Wi-Fi connections
    try:
        connections = subprocess.check_output(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]).decode()
        for line in connections.split('\n'):
            if "802-11-wireless" in line:
                name = line.split(':')[0]
                subprocess.run(["nmcli", "connection", "delete", name])
    except Exception as e:
        pass

    # 2. Delete the stored SimpleAQ device token
    if os.path.exists("/etc/simpleaq/device_token.env"):
        os.remove("/etc/simpleaq/device_token.env")

    # 3. Restart the BLE service to accept new pairing credentials
    subprocess.Popen(["systemctl", "start", "simpleaq-ble.service"])

    return jsonify({"status": "Reset successful. BLE provisioning restarted."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
