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

    # will generate the transaction ids later when we need them to reduce stuff passed in cookies

    # update afs session with order details
    put_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session/{session_id}'
    put_payload = json.dumps({
        "order": {
            "id": order_id,
            "amount": order_amount,
            "currency": order_currency
        }
    })
    put_response = requests.put(put_url, data=put_payload, auth=(afs_user, afs_pass)).json()

    # confirm order details by extracting from put_response - if this is fine we can remove the order details from the local cookie
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
    order_amount = session['order_amount'] # can remove this once i'm done to help clean up
    order_currency = session['order_currency'] # can remove this once i'm done to help clean up

    print("order details from cookie:")
    print("id", order_id)
    print("amount", order_currency, order_amount)

    print("------------------------ begin confirming payment ------------------")

    print("session id is", session_id)

    # now time to generate some transaction ids based on need:

    transaction_id_3ds = secrets.token_hex(8)
    print("transaction id for 3ds is", transaction_id_3ds)

    transaction_id_3ds_auth = secrets.token_hex(8)
    print("transaction id for 3ds auth is", transaction_id_3ds_auth)

    transaction_id_pay = secrets.token_hex(8)
    print("transaction id for payment is", transaction_id_pay)

    auth_token = ""
    auth_available = True

#     # 3DS AUTH BEGINS

    print("----------------------- init 3DS -------------------------")
    
# comment from mastercard website:
# As soon as you have the card number, invoke the Initiate Authentication operation with the payment session identifier. It is recommended that you perform this asynchronously, so that the payer can continue filling out payment details.
# recommended flow: https://afs.gateway.mastercard.com/api/documentation/apiDocumentation/threeds/version/57/api.html?locale=en_US


    init_3ds_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_3ds}'

    init_3ds_payload = json.dumps({
        "apiOperation": "INITIATE_AUTHENTICATION",
        "authentication": {
            "acceptVersions": "3DS1,3DS2",
            "channel": "PAYER_BROWSER",
            "purpose": "PAYMENT_TRANSACTION"
        },
        "correlationId": "test",
        "session": {
            "id": session_id
        },
        "order":{
            "currency": order_currency,
            "reference": order_id
        }
        # ,
        # "transaction":{
        #     "reference": transaction_id_3ds #this must reference t
        # }
	})
        
    init_3ds_res = requests.put(init_3ds_url, data=init_3ds_payload, auth=(afs_user, afs_pass)).json()
    print(json.dumps(init_3ds_res,indent=4,sort_keys=True))
	
    # auth_available = init_3ds_response["transaction"]["authenticationStatus"] == "AUTHENTICATION_AVAILABLE"
    
    print("authentication available", auth_available)

    # only request authentication if available to reduce calls
    if auth_available: 
        print("----------------------- 3DS authentication -------------------------")

        auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_3ds_auth}'

        auth_3ds_payload = json.dumps({
            "apiOperation": "AUTHENTICATE_PAYER",
            "authentication":{
                "redirectResponseUrl":	"https://google.com" # server page to redirect back to once the 3ds process is done?
            },

            "order": {
                "amount": order_amount,
                "currency": order_currency
            },

            "session": {
                "id": session_id
            }
        })

        auth_3ds_res = requests.put(auth_3ds_url, auth=(afs_user, afs_pass), data=auth_3ds_payload).json()
        print(json.dumps(auth_3ds_res,indent=4,sort_keys=True))
	
        # auth_token = auth_3ds_response["authentication"]["3ds"]["authenticationToken"]
        # print("auth token", auth_token)
        # print(auth_3ds_response)

#     3DS AUTH ENDS
    
    print("----------------------- initiating payment ------------------------")

    pay_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_pay}'

    payload_dict = {
        "apiOperation": "PAY",
        "authentication": {
            "transactionId": transaction_id_3ds_auth
        },
        "order": {
            "amount": order_amount,
            "currency": order_currency,
            "reference": order_id
        },
        "transaction": {
            "reference": transaction_id_pay
        },
        "session": {
            "id": session_id
        },

        "sourceOfFunds": {
            "type": "CARD"  
        }
    }

    # if auth_available:
    #     payload_dict['authentication'] = {
    #         "3ds":{
    #             "authenticationToken": auth_token
    #         }
    #     }

    payload = json.dumps(payload_dict)

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
