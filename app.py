import os
import string
import requests
import json
import base64
from flask import (
    Flask, render_template, request, flash, redirect, session, url_for)
if os.path.exists("env.py"):
    import env

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# {{ context_var|tojson|safe }} for using context as js

@app.route('/')
def index():
    url = 'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/TEST100065243/session'
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    payload = json.dumps({
        "session": {
            "authenticationLimit": 25
            
        }
    })
    
    res = requests.post(url, data=payload, auth=(afs_user, afs_pass))
    response = res.json()
    return render_template("index.html", response=response)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5500")),
        debug=True
    )
