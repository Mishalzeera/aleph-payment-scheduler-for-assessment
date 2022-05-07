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

    # # confirm order details by extracting from put_response - if this is fine we can remove the order details from the local cookie
    # print("order details from put response")
    # print("id", put_response['order']['id'])
    # print("amount", put_response['order']['currency'], put_response['order']['amount'])

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
    order_amount = session['order_amount'] # can remove this once i'm done to help clean up
    order_currency = session['order_currency'] # can remove this once i'm done to help clean up

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
        # "correlationId": "test",
        "session": {
            "id": session_id
        }
        # "order":{
        #     "currency": order_currency,
        #     "reference": order_id
        # }
        # ,
        # "transaction":{
        #     "reference": transaction_id_3ds #this must reference t
        # }
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

    # generate transaction id for authentication

    transaction_id_3ds_auth = transaction_id_3ds # secrets.token_hex(8) - must be the same order id and transaction id as the init transaction
    print("transaction id for 3ds auth is", transaction_id_3ds_auth)

    callback_url = "http://127.0.0.1:5500/payment" #hardcoded for now

    print("callback URL is ", callback_url)

    auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_3ds_auth}'

    auth_3ds_payload = json.dumps({
        "apiOperation": "AUTHENTICATE_PAYER",
        "authentication":{
            "redirectResponseUrl":	callback_url # callback doesn't seem to work - the generated HTML doesn't seem to go anywhere...
            # ,"channel": "PAYER_BROWSER" -------- seems to be the default channel
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

        "order": {
            "amount": order_amount,
            "currency": order_currency
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

    context = {

        # "response": auth_3ds_response,
        "session_id": session_id,
        "afs_version": afs_version,
        "merchant_id": afs_url,
        "order_id": order_id,
        "transaction_id": transaction_id_3ds,
        "auth_interaction": auth_interaction
    }

    return render_template("authenticate.html", **context)

@app.route('/payment')
def payment():

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

    print("session id is", session_id)

    print("order details from cookie:")
    print("id", order_id)
    print("amount", order_currency, order_amount)

    # do payment

    transaction_id_pay = secrets.token_hex(8)
    print("transaction id for payment is", transaction_id_pay)

    print("----------------------- initiating payment ------------------------")

    pay_url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/{order_id}/transaction/{transaction_id_pay}'

    payload_dict = {
        "apiOperation": "PAY",
        # "authentication": {
        #     "transactionId": transaction_id_3ds_auth
        # },
        "order": {
            "amount": order_amount,
            "currency": order_currency,
            "reference": order_id
        },
        # "transaction": {
        #     "reference": transaction_id_pay
        # },
        "session": {
            "id": session_id
        },

        "sourceOfFunds": {
            "type": "CARD"  
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
