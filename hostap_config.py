from flask import Flask, render_template, request, make_response, Response, redirect
import dotenv
import getmac
import os
import json
import re
import subprocess
import sqlite3
from localstorage.localsqlite import LocalSqlite

import netifaces as ni

app = Flask(__name__)

def get_mac(interface='wlan0'):
  return ni.ifaddresses(interface)[ni.AF_LINK][0]['addr']

@app.route('/')
def main():
  ssid_re = re.compile("^\s*ssid=\"(.*)\"\s*$")
  psk_re = re.compile("^\s*psk=\"(.*)\"\s*$")

  local_ssid = ""
  with open(os.getenv('wlan_file'), mode='r') as wlan_file:
    for line in wlan_file:
      search_result = ssid_re.match(line)
      if search_result:
        local_ssid = search_result.group(1)

  local_psk = ""
  with open(os.getenv('wlan_file'), mode='r') as wlan_file:
    for line in wlan_file:
      search_result = psk_re.match(line)
      if search_result:
        local_psk = search_result.group(1)

  num_data_points = "Database Error"
  with LocalSqlite(os.getenv("sqlite_db_path")) as local_storage:
    try:
      num_data_points = local_storage.countrecords()
    except Exception:
      # Don't let this break things.
      pass

  return render_template(
      'index.html',
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
      uart_serial_baud=os.getenv('uart_serial_baud'),
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

@app.route('/update/', methods=('GET',))
def update():
  # Maybe update local wifi from a template.
  if (request.args.get('local_wifi_network') != request.args.get('original_local_wifi_network') or
      request.args.get('local_wifi_password') != request.args.get('original_local_wifi_password')):
    # Generate a new wlan configuration.
    # Note that this in no way respects the default configuration set in custom_pigen.
    # If for any reason that changes, this will have to also.
    # However, just in case some users manually edit this, it will never be overwritten unless
    # they actually try to change the values in the form.
    with open(os.getenv('wlan_file'), mode='w') as wlan_file:
      wlan_file.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
      wlan_file.write('update_config=1\n')
      wlan_file.write('network={\n')
      wlan_file.write('    ssid="{}"\n'.format(request.args.get('local_wifi_network')))
      wlan_file.write('    psk="{}"\n'.format(request.args.get('local_wifi_password')))
      wlan_file.write('}\n')

  # Update environment variables.
  keys = ['influx_org', 'influx_bucket', 'influx_token', 'influx_server',
          'simpleaq_interval', 'simpleaq_hostapd_name', 'endpoint_type',
          'simpleaq_hostapd_password', 'hostap_retry_interval_sec',
          'max_backlog_writes', 'i2c_bus', 'uart_serial_baud']

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

  # Remove the HostAP status file so we retry connections on reboot.
  if os.path.exists(os.getenv('hostap_status_file')):
    os.remove(os.getenv('hostap_status_file'))

  # Schedule a Reboot.
  if os.path.exists(os.getenv('reboot_status_file')):
    # Force an immediate reboot.
    os.remove(os.getenv('reboot_status_file'))
    os.system('reboot')
  else:
    # Attempt a soft reboot.
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

@app.route('/debug/hostap/')
def hostap():
  result = subprocess.run(['journalctl', '-u', 'hostap_config.service'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response
