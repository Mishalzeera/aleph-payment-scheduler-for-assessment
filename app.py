import os
from time import process_time_ns
from turtle import goto, setundobuffer
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


@app.route('/carddetails')
def carddetails():

    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

    print("------------------------- init afs session ----------------------------")

    # mastercard session is a json object that is continuously updated by subsequent transactions

    # URL to post initial request to create a session
    post_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session'

    # JSON payload to send in POST request body
    post_payload = json.dumps({
        "session": {
            "authenticationLimit": 25
        }
    })

    # send the POST request and store in "res" variable
    post_res = requests.post(post_url, data=post_payload, auth=(afs_user, afs_pass)).json()

    post_response = json.dumps(post_res,indent=4,sort_keys=True)

    print(post_response)

    # extract the session id
    session_id = post_res['session']['id']

    print("session id is", session_id)

    # and store it in session cookie
    session['afs_session_id'] = session_id
    
    # print("----------------------------------- update session with order details ------------------------")

    # generate order_id and store in the session cookie
    order_id = secrets.token_hex(8)
    order_amount = 2.3
    order_currency = "BHD"
    session['order_id'] = order_id
    session['order_amount'] = order_amount
    session['order_currency'] = order_currency

    # # update afs session with order details
    put_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session/{session_id}'
    put_payload = json.dumps({
        "order": {
            "id": order_id,
            "amount": order_amount,
            "currency": order_currency
        }
    })

    put_res = requests.put(put_url, data=put_payload, auth=(afs_user, afs_pass)).json()

    put_response = json.dumps(put_res,indent=4,sort_keys=True)

    print(put_response)

    # send them to the template 
    context = {
        "response": put_response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id": afs_url
    }

    return render_template("carddetails.html", **context)

@app.route('/authenticate')
def authenticate():
  
    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

    # extract variables from session cookies
    session_id = session['afs_session_id']
    order_id = session['order_id']
     
    # ONLY USEFUL FOR THREEDS JS API LIBRARY - CAN BUNDLE INTO SINGLE REQUEST FOR 3DS SERVER API

    # print("----------------------- updating session with auth details -------------------------")
    
    # # update session with authentication details
    # put_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/session/{session_id}'
    # put_payload = json.dumps({
    #     "authentication": {
    #         "acceptVersions": "3DS1,3DS2",
    #         "channel": "PAYER_BROWSER",
    #         "purpose": "PAYMENT_TRANSACTION",
    #         "redirectResponseUrl":"http://127.0.0.1:5500/payment"
    #     },
    #     # "session": {
    #     #     "id": session_id
    #     # },
    #     # "order":{
    #     #     "currency": order_currency,
    #     #     "reference": order_id
    #     # }
    #     # ,
    #     # "transaction":{
    #     #     "reference": transaction_id_3ds #this must reference t
    #     # }
    # })
    # put_res = requests.put(put_url, data=put_payload, auth=(afs_user, afs_pass)).json()

    # put_response = json.dumps(put_res,indent=4,sort_keys=True)

    # print(put_response)

    # 3DS AUTH BEGINS

    print("----------------------- init 3DS -------------------------")
    
    # comment from mastercard website:
    # As soon as you have the card number, invoke the Initiate Authentication operation with the payment session identifier. It is recommended that you perform this asynchronously, so that the payer can continue filling out payment details.
    # recommended flow: https://afs.gateway.mastercard.com/api/documentation/apiDocumentation/threeds/version/57/api.html?locale=en_US

    # init 3ds transaction - the same transaction number is used for both INITITATE_AUTHENTICATION and AUTHENTICATE_PAYER

    transaction_id_3ds = secrets.token_hex(8)
    print("transaction id for 3ds is", transaction_id_3ds)

    init_3ds_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_3ds}'

    init_3ds_payload = json.dumps({
        "apiOperation": "INITIATE_AUTHENTICATION",
        "authentication": {
            "acceptVersions": "3DS1,3DS2",
            "channel": "PAYER_BROWSER",
            "purpose": "PAYMENT_TRANSACTION"
        },
        "session": {
            "id": session_id
        }
	})
        
    init_3ds_res = requests.put(init_3ds_url, data=init_3ds_payload, auth=(afs_user, afs_pass)).json()

    init_3ds_response = json.dumps(init_3ds_res,indent=4,sort_keys=True)

    print(init_3ds_response)

    # if result is failed, card is most likely not enrolled in any 3DS schene, so update context with error message and render
    if init_3ds_res['result'] != "SUCCESS":
        context = {
            "response": "Gateway reponse is " + init_3ds_res['response']['gatewayCode'],
            "session_id": session_id,
            "afs_version": afs_version,
            "merchant_id:": afs_url
        }
        return render_template("authenticate.html", **context)

    # if above doesn't catch, assume it's a SUCCESS

    print("----------------------- 3DS authentication -------------------------")

    # To increase the likelihood of the authentication being successful, provide as much information about the payer and the transaction as possible.
    #
    # If the information in the request is sufficient to allow the authentication scheme to confirm the payer's identity the response will include the authentication data (frictionless flow).
    # Alternatively (challenge flow), it may be necessary for the payer to interact with the authentication scheme to confirm their identity (e.g. by providing a one-time password sent to them by their card issuer).
    # In this case the response will contain an HTML excerpt that you must inject into your page.
    # This will establish the interaction between the payer and the authentication scheme.
    # After authentication has been completed the payer will be redirected back to your website using the URL provided by you in field authentication.redirectResponseUrl in the Authenticate Payer request.

    # requires device information to generate the browser-sepcific authentication UI code

    # AUTHENTICATE_PAYER must use the same transaction id as INITITATE_AUTHENTICATION

    callback_url = "http://127.0.0.1:5500/payment" #hardcoded for now

    print("callback URL is ", callback_url)

    auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_3ds}'

    auth_3ds_payload = json.dumps({
        "apiOperation": "AUTHENTICATE_PAYER",
        "authentication":{
            "redirectResponseUrl":	callback_url
        },

        "device": {
            "browser": "MOZILLA",# hardcoded - need to extract user-agent from browser
            "browserDetails": {
                "3DSecureChallengeWindowSize": "FULL_SCREEN",# hardcoded - need to extract from browser
                "acceptHeaders": "application/json",
                "colorDepth": 24,# hardcoded - need to extract from browser
                "javaEnabled": True,# hardcoded - need to extract from browser
                "language": "en-US",
                "screenHeight": 640,# hardcoded - need to style the div in the template
                "screenWidth": 480,# hardcoded - need to style the div in the template
                "timeZone": 273 # hardcoded - need to extract from browser
            },
            "ipAddress": "127.0.0.1"
        },
        "session": {
            "id": session_id
        }
    })

    auth_3ds_res = requests.put(auth_3ds_url, auth=(afs_user, afs_pass), data=auth_3ds_payload).json()

    auth_3ds_response = json.dumps(auth_3ds_res,indent=4,sort_keys=True)

    print(auth_3ds_response)

   # if result is PENDING, the next step is to display the 3DS interaction for authententication, otherwise, bomb out

    if auth_3ds_res['result'] != "PENDING":
        print("-------------------- AUTH FAILED ----------------")

        context = {
            "response": "Gateway reponse is " + auth_3ds_res['response']['gatewayCode'],
            "session_id": session_id,
            "afs_version": afs_version,
            "merchant_id:": afs_url
        }
        return render_template("authenticate.html", **context)

    auth_interaction = auth_3ds_res['authentication']['redirectHtml']

    print("------------------------ INJECTING AUTH CODE --------------------")
    print(auth_interaction)
    print("-----------------------------------------------------------------")

    # send code to the template
    # the injected code includes an iframe, so the callback affects the iframe not the actual browser frame.
    # that could still be fine if the payment fails (not enoough funds for example) then stay on the authenticate page and it becomes a catch-all page for card errors?
    # ----------> need to look at other websites for ideas on better "flow"

    # stick it in the cookie for now because i don't know what information comes through in the callback's POST - post might already have this info
    session['transaction_id_3ds'] = transaction_id_3ds

    context = {

        # "response": auth_3ds_response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id": afs_url,
        # order and transaction id only required if using 3DS JS API 
            # "order_id": order_id, 
            # "transaction_id_3ds": transaction_id_3ds,
        # auth_interactio only required if using server side API
        "auth_interaction": auth_interaction
    }

    return render_template("authenticate.html", **context)

@app.route('/payment',methods=["GET","POST"])
def payment():

    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

    # extract variables from session cookies
    session_id = session['afs_session_id']
    order_id = session['order_id'] # may be included in the autentication POST?
    transaction_id_3ds = session['transaction_id_3ds']  # may be included in the autentication POST?

    # do payment

    transaction_id_pay = secrets.token_hex(8)
    print("transaction id for payment is", transaction_id_pay)

    print("----------------------- initiating payment ------------------------")

    pay_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_pay}'

    payload_dict = {
        "apiOperation": "PAY",
        "authentication": {
            "transactionId": transaction_id_3ds
        },
        "session": {
            "id": session_id
        }
    }

    payload = json.dumps(payload_dict)

    pay_res = requests.put(pay_url, data=payload, auth=(afs_user, afs_pass)).json()

    pay_response = json.dumps(pay_res,indent=4,sort_keys=True)

    print(pay_response)

    context = {
        "response": pay_response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id:": afs_url
    }

    return render_template("payment.html", **context)


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5500")),
        debug=True
    )
