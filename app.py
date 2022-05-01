import os
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


@app.route('/alt-payment')
def alt_payment():
    return render_template("alt_payment.html")


@app.route('/payment')
def payment():


    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")

    # URL to post initial request to
    post_url = f'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/{afs_url}/session'

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

    # extract the session id
    session_id = post_response["session"]["id"]
    session['afs_session_id'] = session_id
    

    # create put URL by conc'ing the post_url with the session_id
    put_url = f'{post_url}/{session_id}'

    order_id = secrets.token_hex(16)
    session['order_id'] = order_id

    # add in the payment amount
    put_payload = json.dumps({
        "order": {
            "amount": .1,
            "currency": "BHD",
            "reference": "OrdRef_" + order_id,
        }
    })
    # update the session with the payment amount
    put_response = requests.put(
        put_url, data=put_payload, auth=(afs_user, afs_pass))

    # convert to JSON
    response = put_response.json()
    print(response)
    
    # send them to the template
    context = {
        "response": response,
        "session_id": session_id,
    }

    return render_template("payment.html", **context)


@app.route('/confirm')
def confirm():
    # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")

    # stub_url = 'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/TEST100065243/session'

    order_id = session['order_id']

    # this we randomly generate using secrets 
    transaction_id = secrets.token_hex(8)


    init_3ds_payload = json.dumps({
	"apiOperation":"INITIATE_AUTHENTICATION",
	"authentication":{ 
		"acceptVersions":"3DS1,3DS2",
	    "channel":"PAYER_BROWSER",
	    "purpose":"PAYMENT_TRANSACTION"
	},
	"correlationId":"test",
	"order":{
		"reference": "OrdRef_" + order_id,
    	"currency":"BHD"
	},
	"session": {
		"id": session['afs_session_id']
	},
	"transaction": {
		"reference": "TrxRef_" + transaction_id,
        # "id": "TxnID_" + transaction_id
	}
})
        
    url = f'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/{afs_url}/order/OrdID_{order_id}/transaction/TxnID_{transaction_id}'


    init_3ds_res = requests.put(url, auth=(afs_user, afs_pass), data=init_3ds_payload)

    init_3ds_response = init_3ds_res.json()

    auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/{afs_url}/order/OrdID_{order_id}/transaction/TxnID_{transaction_id}'

    auth_3ds_payload = json.dumps({
	"apiOperation": "AUTHENTICATE_PAYER",
	"authentication":{
		"redirectResponseUrl":	"https://google.com"
	},
	"correlationId":"test",
	"device": {
		"browser": "MOZILLA",
	    "browserDetails": {
			"3DSecureChallengeWindowSize": "FULL_SCREEN",
		    "acceptHeaders": "application/json",
		    "colorDepth": 24,
		    "javaEnabled": "true",
		    "language": "en-US",
		    "screenHeight": 640,
		    "screenWidth": 480,
		    "timeZone": 273
	    },
		"ipAddress": "127.0.0.1"
	},
	"order":{
		"amount":".10",
	    "currency":"BHD"
	},
	"session": {
		"id": session['afs_session_id']
	}
})

    auth_3ds_res = requests.put(auth_3ds_url, auth=(afs_user, afs_pass), data=auth_3ds_payload)

    response = auth_3ds_res.json()

    return render_template("confirm.html", response=response)


# @app.route('/update_alt')
# def update_alt():
#     # auth environment variables
#     afs_user = os.environ.get("AFS_USER")
#     afs_pass = os.environ.get("AFS_PASS")

#     attempt_num = 1

#     body = {"apiOperation": "PAY",
# 	"authentication":{
# 		"transactionId": "TxnID_" + attempt_num
# 	},
# 	"order": {
# 		"amount": 1.00,
# 		"currency": "SAR",
# 		"reference": "OrdRef_" + attempt_num
# 	},
# 	"transaction": {
# 		"reference": "TrxRef_" + attempt_num
#     	},
# 	"session": {
# 		"id": "{{SessionId}}"
# 	},
# 	"sourceOfFunds": {
# 		"type": "CARD"
# 	}
# }

#     payload = json.dumps(body)

#     url = f'https://afs.gateway.mastercard.com/api/rest/version/63/merchant/TEST100065243/order/OrdID_{attempt_num}/transaction/1'
#     try:
#         res = requests.put(url, data=payload, auth=(afs_user, afs_pass))
#         print(res.json())
#     except:
#         if attempt_num < 5:
#             attempt_num += 1
#             res = requests.put(url, data=body, auth=(afs_user, afs_pass))
#         else:
#             return


if __name__ == "__main__":
    app.run(
        host=os.environ.get("IP", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5500")),
        debug=True
    )
