import os
import requests
import jwt
from . import config

# build the URL for the authorization request
def get_authorization_url():
    base_url = config.AUTH_BASE_URL
    client_id = config.CLIENT_ID
    response_type = 'code'
    redirect_uri = config.CALL_BACK_URI
    scope = config.SCOPE

    # Construct the URL
    authorization_url = (
        f"{base_url}?response_type={response_type}"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return authorization_url

# Completes authentication process by swapping the code with the access token. The access token includes the ID token
def exchange_code_for_token(code):
    token_url = config.TOKEN_BASE_URL
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': config.CALL_BACK_URI,
        'client_id': config.CLIENT_ID,
        'client_secret': config.CLIENT_SECRET
    }
    try:
        response = requests.post(token_url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        return response  # Return the response object directly
    except requests.RequestException as e:
        return {"status_code": 400, "text": str(e)}

# Decodes the id token which is a JSON web token to extract the claims associated with the user as well as token specefic information
def decode_id_token(id_token):
    try:
        # Decode the JWT without verification
        decoded = jwt.decode(id_token, options={"verify_signature": False})
        return decoded
    except jwt.ExpiredSignatureError:
        return {'error': 'Expired token'}
    except jwt.PyJWTError as e:
        return {'error': str(e)}

def get_user_info(access_token):
    # get the base url
    base_url = config.USER_INFO_BASE_URL
    if not base_url:
        raise ValueError("USER_INFO_BASE_URL is not set as env variable")
    # set the headers
    headers = {'Authorization': f"Bearer {access_token}"}
    try:
        # send get request
        response = requests.get(base_url, headers=headers)
        #check response was successful
        if response.status_code == 200:
            user_info = response.json()
            return user_info
        else:
            # log the error
            raise Exception(f"Failed to retrieve user info: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        raise Exception(f"Request failed: {str(e)}")