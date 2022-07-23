from flask import Flask, render_template
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
