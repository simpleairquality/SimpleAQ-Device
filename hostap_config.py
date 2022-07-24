from flask import Flask, render_template, request
import dotenv
import os
import re

app = Flask(__name__)

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

  return render_template(
      'index.html',
      local_wifi_network=local_ssid,
      local_wifi_password=local_psk,
      simpleaq_logo='static/simpleaq_logo.png',
      influx_org=os.getenv('influx_org'),
      influx_bucket=os.getenv('influx_bucket'),
      influx_token=os.getenv('influx_token'),
      influx_server=os.getenv('influx_server'),
      simpleaq_interval=os.getenv('simpleaq_interval'),
      simpleaq_hostapd_name=os.getenv('simpleaq_hostapd_name'),
      simpleaq_hostapd_password=os.getenv('simpleaq_hostapd_password'),
      hostap_retry_interval_sec=os.getenv('hostap_retry_interval_sec'),
      max_backlog_writes=os.getenv('max_backlog_writes'))

@app.route('/update/', methods=('POST',))
def update():
  # Maybe update local wifi from a template.
  if (request.form['local_wifi_network'] != request.form['original_local_wifi_network'] or
      request.form['local_wifi_password'] != request.form['original_local_wifi_password']):
    # Generate a new wlan configuration.
    # Note that this in no way respects the default configuration set in custom_pigen.
    # If for any reason that changes, this will have to also.
    # However, just in case some users manually edit this, it will never be overwritten unless
    # they actually try to change the values in the form.
    with open(os.getenv('wlan_file'), mode='w') as wlan_file:
      wlan_file.write('ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n')
      wlan_file.write('update_config=1\n')
      wlan_file.write('network={\n')
      wlan_file.write('    ssid="{}"\n'.format(request.form['local_wifi_network']))
      wlan_file.write('    psk="{}"\n'.format(request.form['local_wifi_password']))
      wlan_file.write('}\n')

  # Update environment variables.
  keys = ['influx_org', 'influx_bucket', 'influx_token', 'influx_server',
          'simpleaq_interval', 'simpleaq_hostapd_name',
          'simpleaq_hostapd_password', 'hostap_retry_interval_sec',
          'max_backlog_writes']

  no_quote_keys = ['simpleaq_hostapd_name', 'simpleaq_hostapd_password']

  for key in keys:
    dotenv.set_key(os.getenv('env_file'), key, request.form[key],
                   quote_mode='never' if key in no_quote_keys else 'always')

  # Reboot.
  os.system('reboot')

  # The user may never see this before the system restarts.
  return render_template('update.html')
