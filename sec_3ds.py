import os 
import json
import requests
from flask import session
if os.path.exists("env.py"):
      import env

def sec_3ds_confirm_call():

      # auth environment variables
    afs_user = os.environ.get("AFS_USER")
    afs_pass = os.environ.get("AFS_PASS")
    afs_url = os.environ.get("AFS_URL")
    afs_version = os.environ.get("AFS_VERSION")

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
        
    url = f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/OrdID_{order_id}/transaction/TxnID_{transaction_id}'


    init_3ds_res = requests.put(url, auth=(afs_user, afs_pass), data=init_3ds_payload)

    init_3ds_response = init_3ds_res.json()

    auth_3ds_url = 	f'https://afs.gateway.mastercard.com/api/rest/version/{afs_version}/merchant/{afs_url}/order/OrdID_{order_id}/transaction/TxnID_{transaction_id}'

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

    pass
