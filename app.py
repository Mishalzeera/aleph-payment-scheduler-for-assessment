import os
from time import process_time_ns
from turtle import setundobuffer
import requests
import json
import secrets
from flask import (
    Flask, render_template, request, flash, redirect, session, url_for)
if os.path.exists("env.py"):
    import env

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# {{ context_var|tojson|safe }} for using context as js


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/payment')
def payment():

    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

    print("------------------------- init afs session ----------------------------")

    # URL to post initial request to
    post_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session'

    # JSON payload to send in POST request body
    post_payload = json.dumps({
        "session": {
            "authenticationLimit": 25
        }
    })

    # send the POST request and store in "res" variable
    res = requests.post(post_url, data=post_payload, auth=(afs_user, afs_pass))

    # convert JSON response to Python dict
    post_response = res.json()

    # print(post_response)

    # extract the session id
    session_id = post_response["session"]["id"]

    print("session id is", session_id)

    # and store it in session cookie
    session['afs_session_id'] = session_id
    
    print("----------------------------------- update session with order details ------------------------")

    # generate order_id and store in the session cookie
    order_id = secrets.token_hex(8)
    order_amount = 1.5
    order_currency = "BHD"
    session['order_id'] = order_id
    session['order_amount'] = order_amount
    session['order_currency'] = order_currency

    # URL to put to
    put_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session/{session_id}'

    # JSON payload to send in PUT request body
    put_payload = json.dumps({
        "order": {
            "id": order_id,
            "amount": order_amount,
            "currency": order_currency
        }
    })

    # send the POST request and store in "res" variable
    res = requests.put(put_url, data=put_payload, auth=(afs_user, afs_pass))

    # convert JSON response to Python dict
    put_response = res.json()

    # print order details to confirm
    print("order details from put response")
    print("id", put_response["order"]["id"])
    print("amount", put_response["order"]["currency"], put_response["order"]["amount"])

    # send them to the template 
    context = {
        "response": put_response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id": afs_url
    }

    return render_template("payment.html", **context)

@app.route('/confirm')
def confirm():
  
    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

    # extract variables from session cookies
    session_id = session['afs_session_id']
    order_id = session['order_id']
    order_amount = session['order_amount']
    order_currency = session['order_currency']

    print("order details from cookie:")
    print("id", order_id)
    print("amount", order_currency, order_amount)

    print("------------------------ begin confirming payment ------------------")

    print("session id is", session_id)
  
    auth_token = ""
    auth_available = False

#     # 3DS AUTH BEGINS

    print("----------------------- init 3DS -------------------------")
    
# comment from mastercard website:
# As soon as you have the card number, invoke the Initiate Authentication operation with the payment session identifier. It is recommended that you perform this asynchronously, so that the payer can continue filling out payment details.
# recommended flow: https://afs.gateway.mastercard.com/api/documentation/apiDocumentation/threeds/version/57/api.html?locale=en_US

    # each request needs a separate transaction id
    transaction_id = secrets.token_hex(8)
    print("transaction id", transaction_id, "init 3ds")

    init_3ds_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id}'

    init_3ds_payload = json.dumps({
        "apiOperation":"INITIATE_AUTHENTICATION",
        "session": {
            "id": session_id
        },
        "order":{
            "currency": order_currency
        }
	})
        
    init_3ds_res = requests.put(init_3ds_url, data=init_3ds_payload, auth=(afs_user, afs_pass))

    init_3ds_response = init_3ds_res.json() 

    # print(init_3ds_response)
	
    auth_available = init_3ds_response["transaction"]["authenticationStatus"] == "AUTHENTICATION_AVAILABLE"
    
    print("authentication available", auth_available)

    # only request authentication if available to reduce calls
    if auth_available: 
        print("----------------------- 3DS authentication -------------------------")

        transaction_id = secrets.token_hex(8)
        print("transaction id", transaction_id, "3ds auth")

        auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id}'

        auth_3ds_payload = json.dumps({
            "apiOperation": "AUTHENTICATE_PAYER",
            "authentication":{
                "redirectResponseUrl":	"https://google.com"
            },

            "order": {
                "amount": order_amount,
                "currency": order_currency
            },

            "session": {
                "id": session_id
            }
        })

        auth_3ds_res = requests.put(auth_3ds_url, auth=(afs_user, afs_pass), data=auth_3ds_payload)
        auth_3ds_response = auth_3ds_res.json()
        auth_token = auth_3ds_response["authentication"]["3ds"]["authenticationToken"]
        print("auth token", auth_token)
        # print(auth_3ds_response)

#     3DS AUTH ENDS
    
    print("--------------------------------------- initiating payment ------------------------")

    transaction_id = secrets.token_hex(8)
    print("transaction id", transaction_id, "pay")

    pay_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id}'

    if auth_available:
        payload = json.dumps({

        "apiOperation": "PAY",
        "authentication":{
            "3ds":{
                "authenticationToken": auth_token
            }
        },

        "order": {
            "amount": order_amount,
            "currency": order_currency
        },

        "session": {
            "id": session_id
        },

        "sourceOfFunds": {
            "type": "CARD"  
        }
        })
    else:
        payload = json.dumps({

        "apiOperation": "PAY",
        "order": {
            "amount": order_amount,
            "currency": order_currency,
        },

        "session": {
            "id": session_id
        },

        "sourceOfFunds": {
            "type": "CARD"  
        }
        })

    response = requests.put(pay_url, data=payload, auth=(afs_user, afs_pass)).json()

    context = {
        "response": response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id:": afs_url
    }

    print(json.dumps(response,indent=4,sort_keys=True))

    # confirmation page is now actually a payment page

    return render_template("confirm.html", **context)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5500")),
        debug=True
    )
