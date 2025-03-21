from flask import Flask, render_template, request, make_response, Response, redirect
import dotenv
import getmac
import os
import json
import re
import subprocess
import sqlite3
import logging
from localstorage.localsqlite import LocalSqlite
from rtlsdr import RtlSdr
import matplotlib.pyplot as plt

import netifaces as ni

app = Flask(__name__)
logger = logging.getLogger(__name__)

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
        logger.error(str(e))
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
        # Connection better already exist, update the SSID and PSK
        subprocess.run(
            ["nmcli", "connection", "modify", connection_name,
             "802-11-wireless.ssid", ssid,
             "802-11-wireless-security.key-mgmt", "wpa-psk",
             "802-11-wireless-security.psk", psk],
            check=True,
            )
    except subprocess.CalledProcessError as e:
        logger.error(str(e))

def get_new_spectrogram(center_freq):
    try:
        sdr = RtlSdr()

        # Configure the SDR
        sdr.sample_rate = 2.048e6  # Hz
        sdr.gain = 'auto'

        # Read samples
        samples = sdr.read_samples(128 * 1024)

        # Plot the spectrogram
        plt.specgram(samples, NFFT=1024, Fs=sdr.sample_rate, noverlap=900)
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.title("RTL-SDR Spectrogram (Center frequency {})".format(center_freq))
        plt.savefig('./static/spec.jpg')

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if 'sdr' in locals():
            sdr.close()


@app.route('/', methods=('GET',))
def main():
    center_freq = request.args.get('frequency')

    cf = 100000000
    if center_freq:
        cf = int(center_freq)

    get_new_spectrogram(cf)

    return render_template(
        'index.html',
        center_frequency=cf)

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
    set_wifi_credentials(request.args.get('local_wifi_network'), 
                         request.args.get('local_wifi_password'))

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
