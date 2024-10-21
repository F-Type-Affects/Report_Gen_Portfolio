import logging
import os
from flask import Flask, redirect, request, session, jsonify
from flask import render_template, redirect, url_for
from flask import flash
import requests
import time

from .auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from .database import setup_database
from .token_manager import save_token_data, get_valid_access_token
from . import config
from .ahj_manager import search_ahj_registry, perform_bing_search

app = Flask(__name__,template_folder='../Front_End_Web/templates', static_folder='../Front_End_Web/static')

app.config['DEBUG'] = False
app.config['SECRET_KEY'] = config.APP_KEY  # Securely generate and store this
app.config['SESSION_TYPE'] = 'filesystem'  # Using server-side session management

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Set up database
DATABASE_PATH = config.DATABASE_PATH
setup_database(DATABASE_PATH)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
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

@app.route('/callback')
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
        
        #adjust expires_in to absolute time
        current_time = int(time.time())
        #set expires in to correct time
        token_data['expires_in'] = int(token_data.get('expires_in', 0)) + current_time
        #set time for refresh token to expire
        token_data['refresh_token_expires_in'] = current_time + 1 * 24 * 3600
        # save extracted token data
        save_token_data(
            sub=sub,  # Assuming 'sub' is available in token_data directly
            email= user_info.get('email'),
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
        return redirect(url_for('home'))
    
    except Exception as e:
        logging.error(f"Error during callback processing: {e}")
        return "An internal error occured.", 500

@app.route('/api/token')
def get_access_token():
    sub = session.get('user_sub')
    if sub is None:
        return jsonify({"error": "User not authenticated"}), 401
    try:
        access_token = get_valid_access_token(sub)  # Assuming this function fetches the token securely
        return jsonify({'access_token': access_token}), 200
    except Exception as e:
        logging.error(f"Error retrieving access token: {e}")
        return jsonify({"error": "Failed to retrieve access token"}), 500


# Route to get AHJ information
@app.route('/get_ahj_info', methods=['POST'])
def get_ahj_info():
    data = request.json
    address = data.get('address')
    
    
    if not address:
        return jsonify({'error': 'Address not provided'}), 400
    
    ahj_info = search_ahj_registry(address)
    
    return jsonify({'ahj_info': ahj_info})
    

# Route to get amendments based on AHJ name
@app.route('/get_amendments', methods=['POST'])
def get_amendments():
    data = request.json
    ahj_name = data.get('ahj_name')
    
    if not ahj_name:
        return jsonify({'error': 'AHJ name not provided'}), 400
    
    query = f"{ahj_name} building code amendments filetype:pdf"
    results = perform_bing_search(query, retries=5)
    
    website_links =[]
    if results:
        for result in results:
            website_links.append(result)
        return jsonify({'amendments': website_links})
    
    return jsonify({'error': 'failed to retrieve ammendments after multiple attempts'}), 500

def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed


if __name__ == '__main__':
    app.run(port=8000)
