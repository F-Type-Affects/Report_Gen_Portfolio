import logging
import os
import webbrowser
import threading
import subprocess
from flask import Flask, redirect, request, session, jsonify
from flask import render_template, redirect, url_for
from flask import flash
from flask_session import Session
from redis import Redis
import requests
import time
from datetime import timedelta

from .auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from .database import setup_database, get_all_emails
from .token_manager import save_token_data, get_valid_access_token
from .project_manager import get_project_by_code, get_client_by_id
from .models import Project, Client
from . import config
from .ahj_manager import search_ahj_registry, perform_bing_search
from .create_project import get_clients_by_name, get_managers_list, create_project_in_bqe

app = Flask(__name__,template_folder='../Front_End_Web/templates', static_folder='../Front_End_Web/static')

# app configuartion
app.config['DEBUG'] = False
app.config['SECRET_KEY'] = config.APP_KEY  # Securely generate and store this
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False  # Set to False so the session expires when the user closes the app
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_USE_SIGNER'] = True  # Encrypt session cookies for extra security
app.config['SESSION_KEY_PREFIX'] = 'sml_report_gen:'  # Optional prefix to help distinguish session keys in Redis
app.config['SESSION_REDIS'] = Redis(host='127.0.0.1', port=6379)  # Connect to your local Redis instance

# setup sessions with redis
Session(app)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Set up database
DATABASE_PATH = config.DATABASE_PATH
setup_database(DATABASE_PATH)

# load the home page of application from template
@app.route('/')
def home():
    return render_template('index.html')

# build authentication url and open login page for user
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

# handle call back response from BQE Core OAuth2 process and exchange code for tokens
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

# get a users access token for API call
@app.route('/api/token')
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

# fetches user email in order to fetch project details
@app.route('/fetch_project_email', methods=['GET', 'POST'])
def fetch_project_email():
    if request.method == 'GET':
        # Fetch emails from the database
        emails = get_all_emails()  # Replace with actual function to get emails
        return render_template('fetch_project_email.html', emails=emails)
    
    elif request.method == 'POST':
        selected_email = request.form['email']
        # Store the selected email in the session for later use
        session['selected_email'] = selected_email
        return redirect(url_for('fetch_project_number'))

# renders template to enter project number and searches project with project number provided
@app.route('/fetch_project_number', methods=['GET', 'POST'])
def fetch_project_number():
    if request.method == 'GET':
        return render_template('fetch_project_number.html')
    
    elif request.method == 'POST':
        selected_email = session.get('selected_email')
        project_number = request.form['project_number']
        
        # Fetch project details from the backend using selected email and project number
        project_data = get_project_by_code(project_number, selected_email)
        
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.')
            return redirect(url_for('fetch_project_number'))
        
        project = Project.from_dict(project_data[0])
        client_data = get_client_by_id(project.client_id, selected_email)
        client = Client.from_dict(client_data[0]) if client_data else None
        
        # Store project details in session
        session['project'] = {
            'street1': project.street1,
            'street2': project.street2,
            'city': project.city,
            'state': project.state,
            'zip_code': project.zip_code
        }
        
        return render_template('fetch_project_details.html', project=project, client=client)

# If user confirms project details display success message
@app.route('/confirm_project_details')
def confirm_project_details():
    flash('Project details confirmed and saved!')
    return redirect(url_for('home'))

# handles getting the address from user to make AHJ search
@app.route('/fetch_ahj_address', methods=['GET', 'POST'])
def fetch_ahj_address():
    if request.method == 'GET':
        # Check if project details are in session
        project_address = None
        if 'project' in session:
            project = session['project']
            project_address = f"{project['street1']}, {project['city']}, {project['state']}, {project['zip_code']}"
        
        return render_template('fetch_ahj_address.html', project_address=project_address)
    
    elif request.method == 'POST':
        if 'use_fetch_flow' in request.form:  # If the user wants to fetch project details
            return redirect(url_for('fetch_project_email'))

        # If user confirmed the project address or manually entered one
        if 'project' in session:
            address = f"{session['project']['street1']}, {session['project']['city']}, {session['project']['state']}, {session['project']['zip_code']}"
        else:
            address = request.form.get('address')
        
        # Store the address in session
        session['address'] = address
        return redirect(url_for('display_ahj_results'))

    elif request.method == 'POST':
        if 'use_fetch_flow' in request.form:  # If the user wants to fetch project details
            return redirect(url_for('fetch_project_email'))

        # If user confirmed the project address or manually entered one
        if 'project' in session:
            address = f"{session['project']['street1']}, {session['project']['city']}, {session['project']['state']}, {session['project']['zip_code']}"
        else:
            address = request.form.get('address')
        
        # Store the address in session
        session['address'] = address
        return redirect(url_for('display_ahj_results'))

# performs the actual AHJ registry search with the address provided from user or other methods
@app.route('/find_ahj', methods=['POST'])
def find_ahj():
    # Logic for finding AHJ
    address = request.form.get('address')

    # Run the AHJ search
    ahj_data = search_ahj_registry(address)

    # Store the results for future use
    session['address'] = address
    session['ahj_data'] = ahj_data

    return render_template('display_ahj_results.html', ahj_data=ahj_data)

# displays the AHJ results to user
@app.route('/display_ahj_results', methods=['GET', 'POST'])
def display_ahj_results():
    # Get the address from the session
    address = session.get('address')

    if not address:
        flash("No address found. Please go back and enter a valid address.")
        return redirect(url_for('fetch_ahj_address'))

    # Run the AHJ search
    ahj_data = search_ahj_registry(address)

    if request.method == 'POST':
        # Store the AHJ data for export
        session['ahj_data'] = ahj_data
        return redirect(url_for('home'))

    # Render the AHJ results
    return render_template('display_ahj_results.html', ahj_data=ahj_data)

# stores the AHJ information to be exported or used later
@app.route('/store_ahj_data', methods=['POST'])
def store_ahj_data():
    # Store AHJ Data for export in the session
    session['ahj_data'] = session.get('ahj_data')
    flash("AHJ data stored for export.")
    return redirect(url_for('home'))

# performs the actual bing search for amendments
@app.route('/search_amendments', methods=['POST'])
def search_amendments():
    # Get the AHJ name from the session or address
    ahj_data = session.get('ahj_data')
    
    if not ahj_data:
        flash("No AHJ data found. Please go back and perform a new search.")
        return redirect(url_for('fetch_ahj_address'))

    # Get the AHJ name for querying amendments
    ahj_name = ahj_data[0]['AHJ Name'] if ahj_data else session.get('address')

    # Perform Bing search for both PDFs and website links
    query = f"{ahj_name} Building Code Amendments"
    pdf_links, web_links = perform_bing_search(query)

    if not pdf_links and not web_links:
        flash("No amendments found.")
        return redirect(url_for('fetch_ahj_address'))

    # Render the results to the user
    return render_template('amendments_results.html', pdf_links=pdf_links, web_links=web_links)

# stores amendment pdf and website links for future use
@app.route('/store_amendment_results', methods=['POST'])
def store_amendment_results():
    # Store both PDF and web links for export later
    session['amendment_pdf_links'] = session.get('pdf_links')
    session['amendment_web_links'] = session.get('web_links')
    flash("Amendment data stored for export.")
    return redirect(url_for('home'))

# landing page for create project where user selects new or existing
@app.route('/create_project', methods=['GET'])
def create_project():
    return render_template('create_project.html')

# landing page for user if they select existing client
@app.route('/create_project/existing_client', methods=['GET'])
def existing_client():
    emails = get_all_emails()
    return render_template('fetch_user_email.html', emails=emails)

# general email selection page to be re-used
@app.route('/create_project/select_email', methods=['POST'])
def select_email():
    selected_email = request.form.get('email')
    session['selected_email'] = selected_email
    return redirect(url_for('find_client'))

# retrieves list of clients with given name
@app.route('/create_project/find_client', methods=['GET', 'POST'])
def find_client():
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('Email not selected. Please start over.')
            return redirect(url_for('existing_client'))

        client_data = get_clients_by_name(client_name, selected_email)
        if client_data and 'items' in client_data and len(client_data['items']) > 0:
            client = client_data['items'][0]
            session['client_id'] = client['id']
            return render_template('display_client.html', client=client)
        else:
            flash('No client found with the provided name.')
            return render_template('display_client.html', client=None)
    else:
        return render_template('find_client.html')

# stores client id for future use
@app.route('/create_project/confirm_client', methods=['POST'])
def confirm_client():
    client_id = request.form.get('client_id')
    session['client_id'] = client_id
    return redirect(url_for('select_manager'))

# allows user to select employee name as manager to get manager id
@app.route('/create_project/select_manager', methods=['GET', 'POST'])
def select_manager():
    if request.method == 'POST':
        manager_id = request.form.get('manager_id')
        session['manager_id'] = manager_id
        return redirect(url_for('enter_project_details'))
    else:
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('Email not selected. Please start over.')
            return redirect(url_for('existing_client'))

        managers = get_managers_list(selected_email)
        return render_template('select_manager.html', managers=managers)

# user enters project details to create and save new project
@app.route('/create_project/enter_project_details', methods=['GET', 'POST'])
def enter_project_details():
    if request.method == 'POST':
        # Get project details from form
        project_code = request.form.get('project_code')
        contract_type = request.form.get('contract_type')
        project_name = request.form.get('project_name')
        project_type = request.form.get('project_type')
        project_address = request.form.get('project_address')
        email = request.form.get('email')
        phone_number = request.form.get('phone_number')

        # Get client_id and manager_id from session
        client_id = session.get('client_id')
        manager_id = session.get('manager_id')
        selected_email = session.get('selected_email')

        if not all([client_id, manager_id, selected_email]):
            flash('Session data missing. Please start over.')
            return redirect(url_for('create_project'))

        # Create the project in BQE Core
        result = create_project_in_bqe(
            project_code,
            contract_type,
            project_name,
            project_type,
            project_address,
            email,
            phone_number,
            client_id,
            manager_id,
            selected_email
        )

        if result:
            flash('Project created successfully!')
            return redirect(url_for('home'))
        else:
            flash('Failed to create project.')
            return redirect(url_for('enter_project_details'))
    else:
        return render_template('project_details.html')


def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed

# clears all session data for the user and returns them to the home page
# should close app but not working
@app.route('/exit_app')
def exit_app():
    session.clear()  # Clear all session data for the user
    flash("You have been logged out. Session data cleared.")
    return redirect(url_for('home'))

# should launch app in its own browser
# is not working
def open_browser():
    time.sleep(2)  # Allow the Flask app to start
    url = 'http://127.0.0.1:8000'
    
    # Command to open Chrome in app mode in a new window
    chrome_command = [
        "chrome.exe",  # Replace with "chrome" or "chrome.exe" if on Windows
        "--new-window",
        f"--app={url}"
    ]
    
    try:
        subprocess.Popen(chrome_command)  # Open Chrome in standalone mode
    except Exception as e:
        logging.error(f"Failed to open Chrome in standalone mode: {e}")
        webbrowser.open(url)  # Fallback to the default browser

# entry point
if __name__ == '__main__':
    # Start the browser-opening function in a separate thread
    threading.Thread(target=open_browser).start()
    # Launch the Flask app
    app.run(port=8000, use_reloader=False)