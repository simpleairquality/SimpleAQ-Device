from flask import Flask, render_template
import os

app = Flask(__name__)

@app.route('/')
def main():
  return render_template(
      'index.html',
      simpleaq_logo='static/simpleaq_logo.png',
      influx_org=os.getenv('influx_org'),
      influx_bucket=os.getenv('influx_bucket'),
      influx_token=os.getenv('influx_token'),
      influx_server=os.getenv('influx_server'),
      simpleaq_interval=os.getenv('simpleaq_interval'),
      simpleaq_hostapd_name=os.getenv('simpleaq_hostapd_name'),
      hostap_retry_interval_sec=os.getenv('hostap_retry_interval_sec'),
      max_backlog_writes=os.getenv('max_backlog_writes'))
