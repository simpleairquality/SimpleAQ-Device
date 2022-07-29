from flask import Flask, render_template, request, make_response, Response, redirect
import dotenv
import os
import json
import re
import subprocess

app = Flask(__name__)

def prevent_hostap_switch():
  subprocess.run(['touch', '/simpleaq/hostap_status_file'])

def get_all_data_files():
  return os.listdir(os.getenv('data_save_path'))

@app.route('/')
def main():
  prevent_hostap_switch()

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

  num_data_points = len(get_all_data_files())

  return render_template(
      'index.html',
      num_data_points=num_data_points,
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

@app.route('/simpleaq.ndjson', methods=('GET',))
def download():
  prevent_hostap_switch()

  touch_every = int(os.getenv('hostap_retry_interval_sec', '100'))

  def generate():
    count = 0
    for file in get_all_data_files():
      count += 1
      if count > touch_every:
        prevent_hostap_switch()
        count = 0
      if os.path.isfile(os.path.join(os.getenv('data_save_path'), file)):
        with open(os.path.join(os.getenv('data_save_path'), file), 'r') as fp:
          # Crunch the data down to a single line.
          try:
            data = json.dumps(json.loads(fp.read()))
            yield data + '\n'
          except Exception:
            # Doesn't matter, don't let a bad file spoil the download.
            pass

  return Response(generate(), mimetype='application/x-ndjson')

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

  # Remove the HostAP status file so we retry connections on reboot.
  if os.path.exists('/simpleaq/hostap_status_file'):
    os.remove('/simpleaq/hostap_status_file')

  # Reboot.
  os.system('reboot')

  # The user may never see this before the system restarts.
  return render_template('update.html')

@app.route("/purge_warn/", methods=('GET',))
def purge_warn():
  prevent_hostap_switch()
  return render_template('purge_warn.html', simpleaq_logo='/static/simpleaq_logo.png')

@app.route("/purge/", methods=('POST',))
def purge():
  prevent_hostap_switch()

  touch_every = int(os.getenv('hostap_retry_interval_sec', 100))

  count = 0
  for file in get_all_data_files():
    count += 1
    if count > touch_every:
      prevent_hostap_switch()
      count = 0
    if os.path.isfile(os.path.join(os.getenv('data_save_path'), file)):
      os.remove(os.path.join(os.getenv('data_save_path'), file))
  return redirect('/')


@app.route('/debug/dmesg/')
def dmesg():
  prevent_hostap_switch()
  result = subprocess.run(['dmesg'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response

@app.route('/debug/simpleaq/')
def simpleaq():
  prevent_hostap_switch()
  result = subprocess.run(['journalctl', '-u', 'simpleaq.service'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response

@app.route('/debug/hostap/')
def hostap():
  prevent_hostap_switch()
  result = subprocess.run(['journalctl', '-u', 'hostap_config.service'], stdout=subprocess.PIPE)
  response = make_response(result.stdout, 200)
  response.mimetype = 'text/plain'
  return response
