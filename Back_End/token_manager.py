import requests
import sqlite3
import jwt
import os
import logging
import time
from .database import execute_query, get_sub_by_email, print_all_tokens
from .config import get_config

config = get_config()

logger = logging.getLogger(__name__)

CLIENT_ID = config.CLIENT_ID
CLIENT_SECRET = config.CLIENT_SECRET
TOKEN_ENDPOINT = config.TOKEN_BASE_URL

def save_token_data(sub, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in, email=None, first_name=None, last_name=None, user_id=None):
    """
    Saves token and user data acquired during the login and authentication process.
    Checks if the user already exists and adds data appropriately.
    """
    # First, check if the entry exists
    logger.info(f"Saving token data for sub: {sub}")
    existing = execute_query(
        "SELECT sub FROM tokens WHERE sub = ?",
        (sub,),
        is_select=True
    )

    if existing:
        # Entry exists, update only the token information
        logger.debug(f"User with sub: {sub} exists. Updating token data.")
        query = """
            UPDATE tokens
            SET id_token = ?, access_token = ?, expires_in = ?, token_type = ?, refresh_token = ?, refresh_token_expires_in = ?
            WHERE sub = ?
        """
        params = (id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in, sub)
        try:
            execute_query(query, params)
        except Exception as e:
            logger.error(f"Error updating token data for sub: {e}")
            raise Exception(f"Database operation failed: {e}")
    else:
        # Entry does not exist, insert new data
        logger.debug(f"User with sub: {sub} does not exist. Inserting new token data.")
        if not email:
            logger.error("Email is required for new token insertion")
            raise Exception("Email is required for new token insertion")
        
        query = """
            INSERT INTO tokens (sub, email, first_name, last_name, user_id, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (sub, email, first_name, last_name, user_id, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
        try:
            execute_query(query, params)
            logger.info(f"Token data successfully saved for sub: {sub}")
        except Exception as e:
            logger.error(f"Error saving new token data for sub: {e}")
            raise Exception(f"Database operation failed: {e}")
    
    print_all_tokens()  # Set to False to limit logging


# extracts token from data base, checks if it is valid, if it is not it refreshes the token
def get_valid_access_token(sub):
    """
    Retrieves a valid access token for the user with the given sub.
    If the current access token is expired, refresh it.
    """
    logger.info(f"Fetching valid access token for sub: {sub}")
    query = """
        SELECT access_token, expires_in, refresh_token FROM tokens WHERE sub = ?
    """
    current_time = int(time.time())
    token_data = execute_query(query, (sub,), is_select=True)
    
    if token_data:
        access_token, expires_in, refresh_token = token_data[0]
        if current_time < expires_in:
            logger.debug("Access token is still valid.")
            return access_token
        else:
            logger.info("Access token expired. Refreshing token.")
            return refresh_access_token(sub, refresh_token)
    else:
        logger.error(f"No token data found for sub: {sub}")
        raise Exception("No token data found for user.")

# refreshes the users access token if it is expired.
def refresh_access_token(sub, refresh_token):
    """
    Uses a refresh token to obtain new access tokens for the given user identifier (sub).
    """
    logger.info(f"Refreshing access token for sub: {sub}")
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    try:
        response = requests.post(TOKEN_ENDPOINT, data=payload)
        if response.status_code == 200:
            logger.debug("Token refresh successful.")
            token_data = response.json()
            current_time = int(time.time())
            token_data['expires_in'] = int(token_data.get('expires_in',0)) + current_time
            token_data['refresh_token_expires_in'] = current_time + 1 * 24 * 3600

            save_token_data(
                sub=sub,
                id_token=token_data['id_token'],
                access_token=token_data['access_token'],
                expires_in=token_data['expires_in'],
                token_type=token_data['token_type'],
                refresh_token=token_data['refresh_token'],
                refresh_token_expires_in=token_data['refresh_token_expires_in']
            )
            return token_data.get('access_token', '')
        else:
            logger.error(f"Failed to refresh access token for sub {sub}: {response.text}")
            raise Exception('Failed to refresh token')
    except requests.RequestException as e:
        logger.error(f"RequestException during refresh_access_token: {str(e)}")
        raise Exception(f"Request failed: {str(e)}")

# verifies the access token so that it can be decoded
def validate_token(access_token):
    """
    Validates the access token.
    """
    logger.info("Validating access token.")
    try:
        jwt.decode(access_token, options={"verify_signature": False})  # Simplified; in production, verify the signature
        logger.debug("Access token is valid.")
    except jwt.InvalidTokenError as e:
        logger.error(f'Invalid token: {e}')
        raise Exception('Token validation failed')

# fetches the token from the data base. 
def fetch_access_token(sub):
    
    logger.info(f"Fetching access token for sub: {sub}")
    if not sub:
        logger.error("Sub is missing. User not authenticated.")
        raise Exception("User not authenticated")

    try:
        access_token = get_valid_access_token(sub)
        logger.debug("Access token fetched successfully.")
        return access_token
    except Exception as e:
        logger.error(f"Failed to fetch access token for sub: {sub}: {e}")
        raise Exception(f"Failed to fetch access token: {str(e)}")

def fetch_access_token_by_email(email):
    """
    Retrieves a valid access token using the user's email.
    Args:
        email (str): The email of the authenticated user.
    Returns:
        str: A valid access token.
    """
    logger.info(f"Fetching access token for email: {email}")
    sub = get_sub_by_email(email)
    if not sub:
        logger.error(f"No sub found for email: {email}")
        raise Exception("User not authenticated")
    return fetch_access_token(sub)