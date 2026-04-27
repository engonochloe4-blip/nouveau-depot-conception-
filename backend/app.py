import os
import sys

from flask import Flask, jsonify

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from vmware_client import get_vmware_status, list_vms


app = Flask(__name__)


@app.route("/")
def index():
    return "OK"


@app.route("/vmware/status")
def vmware_status():
    try:
        return jsonify(get_vmware_status())
    except Exception as exc:
        return jsonify(error=str(exc)), 500


@app.route("/vmware/vms")
def vmware_vms():
    try:
        return jsonify(vms=list_vms())
    except Exception as exc:
        return jsonify(error=str(exc)), 500


if __name__ == "__main__":
    app.run(debug=True)
