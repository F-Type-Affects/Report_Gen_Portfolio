# app/api/routes/auth_routes.py
# ================================
"""
Authentication routes for BQE CORE OAuth2 integration
Handles login, logout, token management, and user selection
"""

from flask import Blueprint, redirect, request, session, jsonify, render_template, url_for, flash
import logging
import time
import requests
import uuid
from threading import Thread

# Import from your new structure
from app.auth.auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from app.auth.token_manager import save_token_data, get_valid_access_token
from app.core.database import get_all_emails, get_user_details_by_email
from app.core.config import get_config

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Get configuration and logger
config = get_config()
logger = logging.getLogger(__name__)

# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================
"""App route to the home page of web application index.html""" 
@auth_bp.route('/')
def home():
    return render_template('index.html')

"""End of home route"""

"""
These app routes handle the login and authentication process to the BQE CORE Platform.
This process grants access to the application for the user as well as saves the relevant user information
in a simple SQLite table so they do not need to do this everytime they use the application
"""
@auth_bp.route('/login')
def login():
    # Check client_id directly
    client_id = config.CLIENT_ID
    if not client_id:
        logger.error("CLIENT_ID is not set.")
    else:
        logger.info(f"Client ID Set")

    # Get the authorization URL from the auth module
    auth_url = get_authorization_url()

    # Redirect the user to the BQE Core authorization page
    return redirect(auth_url)

# handle call back response from BQE Core OAuth2 process and exchange code for tokens
@auth_bp.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "Authorization code not found", 400

    token_response = exchange_code_for_token(code)
    if not isinstance(token_response, requests.Response):
        return f"Error during token exchange: {token_response['text']}", token_response['status_code']

    if token_response.status_code != 200:
        return f"Failed to retrieve token: {token_response.status_code} - {token_response.text}", token_response.status_code

    try:
        #get token data
        token_data = token_response.json()
        #decode the id token
        decoded_id_token = decode_id_token(token_data['id_token'])
        # extract the sub and email
        sub = decoded_id_token.get('sub')
        if not sub:
            return "Sub not found in the ID token", 400
        
        # get access token
        access_token = token_data.get('access_token')
        if not access_token:
            return "Access token not found in token data", 400
        
        # get user info
        user_info = get_user_info(access_token)
        if not user_info:
            return "Failed to retrieve user info.", 500
        
        logger.debug("User Info: %s", user_info)
        
        # Extract required user information
        email = user_info.get('email')
        first_name = user_info.get('given_name')
        last_name = user_info.get('family_name')
        user_id = user_info.get('user_id')  # Assuming 'user_id' is present
        
        if not all([email, first_name, last_name, user_id]):
            logger.error("Missing user information from user_info")
            return "Incomplete user information received.", 400
        
        #adjust expires_in to absolute time
        current_time = int(time.time())
        
        #set expires in to correct time
        token_data['expires_in'] = int(token_data.get('expires_in', 0)) + current_time
        
        #set time for refresh token to expire
        token_data['refresh_token_expires_in'] = current_time + 1 * 24 * 3600
        
        # Save extracted token and user data
        save_token_data(
            sub=sub,
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_id=user_id,
            id_token=token_data.get('id_token'),
            access_token=token_data.get('access_token'),
            expires_in=token_data.get('expires_in'),
            token_type=token_data.get('token_type'),
            refresh_token=token_data.get('refresh_token'),
            refresh_token_expires_in=token_data.get('refresh_token_expires_in')
        )
        login_user(sub)
        
        # Flash success message
        flash("Login successful! You can now use the application.")
        
        # Redirect to the home page (index.html) with a success message
        return redirect(url_for('auth.home'))
    
    except Exception as e:
        logging.error(f"Error during callback processing: {e}")
        return "An internal error occured.", 500

# get a users access token for API call
@auth_bp.route('/api/token')
def get_access_token():
    sub = session.get('user_sub')
    if sub is None:
        return jsonify({"error": "User not authenticated"}), 401
    try:
        access_token = get_valid_access_token(sub)  # function to fetch token
        return jsonify({'access_token': access_token}), 200
    except Exception as e:
        logging.error(f"Error retrieving access token: {e}")
        return jsonify({"error": "Failed to retrieve access token"}), 500

"""
End of Authentication routes
"""
# =============================================================================
# USER EMAIL SELECTION ROUTES
# =============================================================================
"""
These routes handle selecting the user email which is used to retrieve the user's sub, acces, and id tokens
and required to query the BQE Core Platforms enbdpoints
"""
@auth_bp.route('/select_user_email_get', methods=['GET'])
def select_user_email_get():
    emails = get_all_emails()  # Retrieve emails from the database
    next_url = request.args.get('next', 'display_project_client_details')
    return render_template('select_user_email.html', emails=emails, next_url=next_url)

@auth_bp.route('/select_user_email_post', methods=['POST'])
def select_user_email_post():
    selected_email = request.form.get('email')
    next_url = request.form.get('next_url')
    
    if not selected_email:
        flash('Please select an email.', 'error')
        return redirect(url_for('auth.select_user_email_get'))
    
    # Store the selected email in the session
    session['selected_email'] = selected_email
    flash(f'Email "{selected_email}" selected successfully.', 'success')

    return redirect(url_for('project.fetch_project_number_get', next=next_url))

"""
End of email app routes
"""
# =============================================================================
# LOGOUT ROUTE
# =============================================================================
# clears all session data for the user and returns them to the home page
@auth_bp.route('/exit_app')
def exit_app():
    """
    Clear all session data for the user and return them to the home page
    """
    session.clear()  # Clear all session data for the user
    flash("You have been logged out. Session data cleared.")
    return redirect(url_for('auth.home'))

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
"""Helper functions to get specefic user data for calls to endpoints"""
def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed