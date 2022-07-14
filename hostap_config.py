from flask import Flask

app = Flask(__name__)


@app.route('/')
def hello():
  return 'This will be the SimpleAQ HostAP configuration tool.'
