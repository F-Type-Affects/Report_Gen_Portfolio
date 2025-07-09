import os
import requests
import logging
import jwt
from app.core.config import get_config

config = get_config()

logger = logging.getLogger(__name__)

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
    logger.debug(f"Authorization URL: {authorization_url}")
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
        logging.info("Exchanging Authorization code for token")
        response = requests.post(
            token_url, data=data, 
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
        logger.debug(f"Token exchange response status: {response.status_code}")
        if response.status_code != 200:
            logger.warning(f"Token exchange failed: {response.status_code} - {response.text}")
        return response  # Return the response object directly
    except requests.RequestException as e:
        logger.error(f"Error during token exchange: {e}")
        return {"status_code": 400, "text": str(e)}

# Decodes the id token which is a JSON web token to extract the claims associated with the user as well as token specefic information
def decode_id_token(id_token):
    try:
        # Decode the JWT without verification
        decoded = jwt.decode(id_token, options={"verify_signature": False})
        logger.debug("ID token successfully decoded.")
        return decoded
    except jwt.ExpiredSignatureError:
        logger.error("ID token has expired.")
        return {'error': 'Expired token'}
    except jwt.PyJWTError as e:
        logger.error(f"Error decoding ID token: {e}")
        return {'error': str(e)}

def get_user_info(access_token):
    # get the base url
    base_url = config.USER_INFO_BASE_URL
    
    if not base_url:
        logger.error("USER_INFO_BASE_URL is not set as an environment variable.")
        raise ValueError("USER_INFO_BASE_URL is not set as env variable")
    # set the headers
    headers = {'Authorization': f"Bearer {access_token}"}
    logger.info("Fetching user info.")
    try:
        # send get request
        response = requests.get(base_url, headers=headers)
        logger.debug(f"User info response status: {response.status_code}")
        #check response was successful
        if response.status_code == 200:
            user_info = response.json()
            logger.info("User info successfully retrieved.")
            return user_info
        else:
            # log the error
            logger.warning(f"Failed to retrieve user info: {response.status_code} - {response.text}")
            raise Exception(f"Failed to retrieve user info: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"Request for user info failed: {e}")
        raise Exception(f"Request failed: {str(e)}")