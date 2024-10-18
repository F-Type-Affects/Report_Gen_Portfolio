import requests
import sqlite3
import jwt
import os
import logging
import time
from .database import execute_query, get_sub_by_email
from . import config

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Load environment variables
CLIENT_ID = config.CLIENT_ID
CLIENT_SECRET = config.CLIENT_SECRET
TOKEN_ENDPOINT = config.TOKEN_BASE_URL

# Saves token and user data aquired during the login and authentication process. Checks if the user already exists and adds data appropriately
def save_token_data(sub, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in, email=None):
    """
    checks if the users sub already exist in the database or not. If it does, then it updates the table with only necessary data.
    if the sub is not in the database it will update the table as if it is a new user
    """
    # First, check if the entry exists
    existing = execute_query(
        "SELECT sub FROM tokens WHERE sub = ?",
        (sub,),
        is_select=True
    )

    if existing:
        # Entry exists, update only the token information
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
        # check for email
        if not email:
            logger.error(f"Email is required for new token insertion")
            raise Exception("Email is required for new token insertion")
        
        query = """
            INSERT INTO tokens (sub, email, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (sub, email, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
        try:
            execute_query(query, params)
        except Exception as e:
            logger.error(f"Error saving new token data for sub: {e}")
            raise Exception(f"Database operation failed: {e}")

# extracts token from data base, checks if it is valid, if it is not it refreshes the token
def get_valid_access_token(sub):
    """
    Retrieves a valid access token for the user with the given sub.
    If the current access token is expired, refresh it.
    """
    query = """
        SELECT access_token, expires_in, refresh_token FROM tokens WHERE sub = ?
    """
    current_time = int(time.time())
    token_data = execute_query(query, (sub,), is_select=True)
    
    if token_data:
        access_token, expires_in, refresh_token = token_data[0]
        if current_time < expires_in:
            return access_token
        else:
            return refresh_access_token(sub, refresh_token)
    else:
        raise Exception("No token data found for user.")

# refreshes the users access token if it is expired.
def refresh_access_token(sub, refresh_token):
    """
    Uses a refresh token to obtain new access tokens for the given user identifier (sub).
    """
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    try:
        response = requests.post(TOKEN_ENDPOINT, data=payload)
        if response.status_code == 200:
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
    try:
        jwt.decode(access_token, options={"verify_signature": False})  # Simplified; in production, verify the signature
    except jwt.InvalidTokenError as e:
        logger.error(f'Invalid token: {e}')
        raise Exception('Token validation failed')

# fetches the token from the data base. 
def fetch_access_token(sub):
    
    if not sub:
        raise Exception("User not authenticated")

    try:
        access_token = get_valid_access_token(sub)
        return access_token
    except Exception as e:
        raise Exception(f"Failed to fetch access token: {str(e)}")

def fetch_access_token_by_email(email):
    """
    Retrieves a valid access token using the user's email.
    Args:
        email (str): The email of the authenticated user.
    Returns:
        str: A valid access token.
    """
    sub = get_sub_by_email(email)
    if not sub:
        raise Exception("User not authenticated")
    return fetch_access_token(sub)