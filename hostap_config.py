from flask import Flask, render_template, request, make_response, Response, redirect
import dotenv
import getmac
import os
import json
import re
import shlex
import subprocess
import sqlite3
import logging
from localstorage.localsqlite import LocalSqlite

import netifaces as ni

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

def get_mac(interface='wlan0'):
  return ni.ifaddresses(interface)[ni.AF_LINK][0]['addr']

def get_wifi_field(field):
    """Retrieve the PSK for a given connection name."""
    try:
        # "Wifi" set in files/wifi.nmconnection
        result = subprocess.run(
            ["sudo", "nmcli", "-s", "-g", field, "connection", "show", "Wifi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        app.logger.error(str(e))
    return ""

def set_wifi_credentials(ssid, psk, connection_name="Wifi"):
    """
    Set or update the Wi-Fi credentials (SSID and PSK) for a connection.

    Parameters:
        ssid (str): The SSID of the Wi-Fi network.
        psk (str): The password for the Wi-Fi network.
        connection_name (str): The name of the connection profile (optional).
                               If not provided, defaults to the SSID.
    """
    if not connection_name:
        connection_name = ssid  # Use SSID as connection name if none provided

    try:
        if psk:
          # Connection better already exist, update the SSID and PSK
          subprocess.run(
              ["nmcli", "connection", "modify", connection_name,
               "802-11-wireless.ssid", ssid,
               "802-11-wireless-security.key-mgmt", "wpa-psk",
               "802-11-wireless-security.psk", psk],
              check=True,
              )
        else:
          # If no password is provided, connect without one.
          subprocess.run(
              ["nmcli", "connection", "modify", connection_name,
               "802-11-wireless.ssid", ssid],
              check=True,
              )

          subprocess.run(
              ["nmcli", "connection", "modify", connection_name,
               "remove", "802-11-wireless-security"],
              check=True,
          )

    except subprocess.CalledProcessError as e:
        app.logger.error(str(e))

@app.route('/')
def main():
  ssid_re = re.compile("^\s*ssid=\"(.*)\"\s*$")
  psk_re = re.compile("^\s*psk=\"(.*)\"\s*$")

  local_ssid = get_wifi_field('802-11-wireless.ssid')
  local_psk = get_wifi_field('802-11-wireless-security.psk') 

  num_data_points = "Database Error"
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:
    try:
      num_data_points = local_storage.countrecords()
    except Exception:
      # Don't let this break things.
      pass

  warn_message = ''
  if os.path.exists(os.getenv('reboot_status_file')):
    warn_message = 'These settings may be out of date, as previous settings are still being applied.  Please refresh this page in a few minutes for up to date settings.'

  return render_template(
      'index.html',
      warn_message=warn_message,
      num_data_points=num_data_points,
      local_wifi_network=local_ssid,
      local_wifi_password=local_psk,
      endpoint_type_simpleaq="selected" if os.getenv('endpoint_type') == "SIMPLEAQ" else "",
      endpoint_type_influxdb="selected" if os.getenv('endpoint_type') == "INFLUXDB" else "",
      influx_options_disabled="" if os.getenv('endpoint_type') == "INFLUXDB" else "disabled",
      simpleaq_logo='static/simpleaq_logo.png',
      influx_org=os.getenv('influx_org'),
      influx_bucket=os.getenv('influx_bucket'),
      influx_token=os.getenv('influx_token'),
      influx_server=os.getenv('influx_server'),
      simpleaq_interval=os.getenv('simpleaq_interval'),
      simpleaq_hostapd_name=os.getenv('simpleaq_hostapd_name'),
      simpleaq_hostapd_password=os.getenv('simpleaq_hostapd_password'),
      simpleaq_hostapd_hide_ssid_checked=('checked' if os.getenv('simpleaq_hostapd_hide_ssid') == '1' else ''),
      hostap_retry_interval_sec=os.getenv('hostap_retry_interval_sec'),
      max_backlog_writes=os.getenv('max_backlog_writes'),
      detected_devices=os.getenv('detected_devices'),
      i2c_bus=os.getenv('i2c_bus'),
      mac_addr=str(get_mac()))

@app.route('/simpleaq.ndjson', methods=('GET',))
def download():
  touch_every = int(os.getenv('hostap_retry_interval_sec', '100'))

  def generate(connection, cursor):
    count = 0
    data = cursor.fetchone()

    while data:
      try:
        # Maybe prevent HostAP switching during a large download.
        count += 1
        if count > touch_every:
          count = 0

        # Make sure we only return valid JSON
        data_jsonstr = json.dumps(json.loads(data[1]))
        yield data_jsonstr + '\n'
      except Exception:
        # Doesn't matter, don't let a bad file spoil the download.
        pass

      data = cursor.fetchone()

    cursor.close()
    connection.close()

  # Make sure there's a place to actually put the backlog database if necessary.
  os.makedirs(os.path.dirname(os.getenv("sqlite_db_path")), exist_ok=True)

  # Implcitly create the database.
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:
    pass

  # No, we cannot use contextlib.closing or a with block here.
  # The WSGI middleware in the streaming response generator will close them before
  # generate can be called!  
  # There is no clear path to refactor this into the local_storage paradigm.
  # TODO:  Figure out a way.  Maybe if "generate" existed within the "with" block?
  # That would be weird but might just work.

  # This implicitly creates the database.
  db_conn = sqlite3.connect(os.getenv("sqlite_db_path"))

  # OK, we need a table to store backlog data if it doesn't exist.
  cursor = db_conn.cursor()
  cursor.execute("SELECT * FROM data")

  return Response(generate(db_conn, cursor), mimetype='application/x-ndjson')

def get_psk(ssid, password):
  cmd = f"wpa_passphrase {shlex.quote(ssid)} {shlex.quote(password)}"
  psk_output = subprocess.check_output(cmd, shell=True, text=True)

  # Extract the 'psk=' line that is *not* the commented passphrase
  psk_line = next(line for line in psk_output.splitlines() if line.strip().startswith("psk=") and not line.strip().startswith("#"))
  psk_value = psk_line.split("=", 1)[1]

  return psk_value

@app.route('/update/', methods=('GET',))
def update():
  new_local_wifi_psk = None
  
  new_local_wifi_network = request.args.get('local_wifi_network')
  new_local_wifi_password = request.args.get('local_wifi_password')
  original_local_wifi_network = request.args.get('original_local_wifi_network')
  original_local_wifi_password = request.args.get('original_local_wifi_password')

  # Check if WiFi settings changed
  wifi_changed = (new_local_wifi_network != original_local_wifi_network or
                  new_local_wifi_password != original_local_wifi_password)

  if wifi_changed and new_local_wifi_network:
    if new_local_wifi_password == '':
      # Explicitly empty = open network
      new_local_wifi_psk = ''
    elif len(new_local_wifi_password) < 8:
      # This is not normally a valid thing, leading to an HTTP 500 when get_psk fails.
      # Let them try I guess.
      new_local_wifi_psk = new_local_wifi_password
    elif len(new_local_wifi_password) < 64:
      # Short password = needs hashing
      new_local_wifi_psk = get_psk(new_local_wifi_network, new_local_wifi_password)
    else:
      # 64 chars = already a PSK
      new_local_wifi_psk = new_local_wifi_password

    set_wifi_credentials(new_local_wifi_network, new_local_wifi_psk)

  # Update environment variables.
  keys = ['influx_org', 'influx_bucket', 'influx_token', 'influx_server',
          'simpleaq_interval', 'simpleaq_hostapd_name', 'endpoint_type',
          'simpleaq_hostapd_password', 'hostap_retry_interval_sec',
          'max_backlog_writes', 'i2c_bus']

  no_quote_keys = ['simpleaq_hostapd_name', 'simpleaq_hostapd_password']

  for key in keys:
    if key in request.args.keys():
      dotenv.set_key(os.getenv('env_file'), key, request.args.get(key),
                     quote_mode='never' if key in no_quote_keys else 'always')

  # Checkbox needs to be handled separately.
  dotenv.set_key(
      os.getenv('env_file'),
      'simpleaq_hostapd_hide_ssid',
      request.args.get('simpleaq_hostapd_hide_ssid', '0'),
      quote_mode='never')

  # Update hostapd settings if requested.  It will be rebooted by SimpleAQ services.
  if request.args.get('simpleaq_hostapd_name'):
    os.system('sed -i -s "s/^\s*ssid=.*/ssid={}/" /etc/hostapd/hostapd.conf'.format(request.args.get('simpleaq_hostapd_name')))
  if request.args.get('simpleaq_hostapd_password') is not None:
    os.system('sed -i -s "s/^\s*wpa_passphrase=.*/wpa_passphrase={}/" /etc/hostapd/hostapd.conf'.format(request.args.get('simpleaq_hostapd_password')))
  os.system('sed -i -s "s/^\s*ignore_broadcast_ssid=.*/ignore_broadcast_ssid={}/" /etc/hostapd/hostapd.conf'.format(request.args.get('simpleaq_hostapd_hide_ssid', '0')))

  # Schedule a Reboot.
  os.system('touch {}'.format(os.getenv('reboot_status_file')))

  # The user may never see this before the system restarts.
  return render_template('update.html')

@app.route("/purge_warn/", methods=('GET',))
def purge_warn():
  return render_template('purge_warn.html', simpleaq_logo='/static/simpleaq_logo.png')

@app.route("/purge/", methods=('POST',))
def purge():
  # Make sure there's a place to actually put the backlog database if necessary.
  os.makedirs(os.path.dirname(os.getenv("sqlite_db_path")), exist_ok=True)

  # This implicitly creates the database.
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:
    local_storage.deleteall()

  return redirect('/')


@app.route('/debug/dmesg/')
def dmesg():
  result = subprocess.run(['dmesg'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response

@app.route('/debug/simpleaq/')
def simpleaq():
  result = subprocess.run(['journalctl', '-u', 'simpleaq.service'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response

@app.route('/debug/networkmanager/')
def networkmanager():
  result = subprocess.run(['journalctl', '-u', 'NetworkManager'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response

@app.route('/debug/hostap/')
def hostap():
  result = subprocess.run(['journalctl', '-u', 'hostap_config.service'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response
