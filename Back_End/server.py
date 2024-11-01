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
from .create_project import get_clients_by_name, get_employees, fetch_manager_id, send_create_project_request
from .export_project_details import create_workbook, insert_project_data, insert_client_data, save_workbook, insert_ahj_data

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

##############################################################
# load the home page of application from template
@app.route('/')
def home():
    return render_template('index.html')


#####################################################################
# routes to select user's email which is required to retrieve user sub which is required for API calls to CORE
@app.route('/select_email', methods=['GET'])
def select_email():
    # Retrieve the 'next' parameter from the query string
    next_url = request.args.get('next')
    
    if not next_url:
        flash('No destination specified for email selection.', 'error')
        return redirect(url_for('home'))
    
    # Fetch emails from the database
    emails = get_all_emails()
    
    return render_template('select_email.html', emails=emails, next_url=next_url)

@app.route('/select_email_submit', methods=['POST'])
def select_email_submit():
    selected_email = request.form.get('email')
    next_url = request.form.get('next_url')
    
    if not selected_email:
        flash('Please select an email.', 'error')
        return redirect(request.referrer or url_for('select_email', next=next_url))
    
    # Store the selected email in the session
    session['selected_email'] = selected_email
    flash(f'Email "{selected_email}" selected successfully.', 'success')
    
    if next_url:
        return redirect(next_url)
    else:
        flash('No destination specified after email selection.', 'error')
        return redirect(url_for('home'))

############################
# login and authentication app routes

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

######################################################
# app route to fetch project and client details to export

# GET route to display project number entry form
@app.route('/fetch_project_number', methods=['GET'])
def fetch_project_number_get():
    return render_template('fetch_project_number.html')

# POST route to handle project number submission
@app.route('/fetch_project_number_submit', methods=['POST'])
def fetch_project_number_post():
    selected_email = session.get('selected_email')
    if not selected_email:
        flash('No email selected. Please select an email first.', 'error')
        return redirect(url_for('fetch_project_email_get'))
    
    project_number = request.form.get('project_number')
    if not project_number:
        flash('Please enter a project number.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Fetch project details from the backend using selected email and project number
    project_data = get_project_by_code(project_number, selected_email)
    
    if not project_data:
        flash('Project not found. Please check the Project ID and try again.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
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

#####################################################
# app routes to search AHJ registry and Bing for amendments to build codes

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

# GET route to display AHJ address form
@app.route('/fetch_ahj_address', methods=['GET'])
def fetch_ahj_address_get():
    # Check if project details are in session
    project_address = None
    if 'project' in session:
        project = session['project']
        project_address = f"{project['street1']}, {project['city']}, {project['state']}, {project['zip_code']}"
    
    return render_template('fetch_ahj_address.html', project_address=project_address)

# POST route to handle AHJ address submission
@app.route('/fetch_ahj_address_submit', methods=['POST'])
def fetch_ahj_address_post():
    if 'use_fetch_flow' in request.form:  # If the user wants to fetch project details
        return redirect(url_for('fetch_project_email_get'))
    
    # If user confirmed the project address or manually entered one
    if 'project' in session:
        address = f"{session['project']['street1']}, {session['project']['city']}, {session['project']['state']}, {session['project']['zip_code']}"
    else:
        address = request.form.get('address')
        if not address:
            flash('Please enter an address.', 'error')
            return redirect(url_for('fetch_ahj_address_get'))
    
    # Store the address in session
    session['address'] = address
    return redirect(url_for('display_ahj_results'))

@app.route('/display_ahj_results', methods=['GET'])
def display_ahj_results():
    address = session.get('address')
    if not address:
        flash('No address found. Please enter an address first.', 'error')
        return redirect(url_for('fetch_ahj_address_get'))
    
    # Placeholder for AHJ search logic
    ahj_results = search_ahj_registry(address)  # Assume this function is defined elsewhere
    
    return render_template('display_ahj_results.html', ahj_results=ahj_results)

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

# GET route to display AHJ results
@app.route('/display_ahj_results', methods=['GET'])
def display_ahj_results_get():
    # Get the address from the session
    address = session.get('address')

    if not address:
        flash("No address found. Please go back and enter a valid address.", 'error')
        return redirect(url_for('fetch_ahj_address_get'))

    # Run the AHJ search
    ahj_data = search_ahj_registry(address)

    return render_template('display_ahj_results.html', ahj_data=ahj_data)

# POST route to handle AHJ results submission
@app.route('/display_ahj_results_submit', methods=['POST'])
def display_ahj_results_post():
    # Get the address from the session
    address = session.get('address')

    if not address:
        flash("No address found. Please go back and enter a valid address.", 'error')
        return redirect(url_for('fetch_ahj_address_get'))

    # Run the AHJ search
    ahj_data = search_ahj_registry(address)

    if not ahj_data:
        flash("No AHJ data found for the provided address.", 'error')
        return redirect(url_for('fetch_ahj_address_get'))

    # Store the AHJ data for export
    session['ahj_data'] = ahj_data
    flash("AHJ data has been saved for export.", 'success')
    return redirect(url_for('home'))

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

########################################################
# app routes to create project

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
    return redirect(url_for('find_client_landing'))

@app.route('/create_project/find_client', methods=['GET'])
def find_client_landing():
    return render_template('find_client_landing.html')


@app.route('/create_project/search_client', methods=['GET'])
def search_client():
    # Use request.args.get for GET requests to retrieve query parameters
    client_name = request.args.get('client_name')
    
    selected_email = session.get('selected_email')
    if not selected_email:
        flash('Email not selected. Please start over.')
        return redirect(url_for('find_client_landing'))

    if client_name is None:
        flash("Client name not provided.")
        return redirect(url_for('find_client_landing'))

    # Proceed with the API call to fetch client data
    client_data = get_clients_by_name(client_name, selected_email)

    if client_data and len(client_data) > 0:
        client = client_data[0]  # Access the first client directly
        session['client_id'] = client['id']
        return render_template('display_client.html', client=client)
    else:
        flash('No client found with the provided name.')
        return render_template('display_client.html', client=None)

@app.route('/create_project/confirm_client', methods=['POST'])
def confirm_client():
    client_id = request.form.get('client_id')
    session['client_id'] = client_id  # Store the client_id in the session for future use
    return redirect(url_for('select_employee'))

# GET route to display the project details form
@app.route('/create_project/enter_project_details', methods=['GET'])
def enter_project_details_get():
    return render_template('project_details.html')

# POST route to handle project details submission
@app.route('/create_project/enter_project_details_submit', methods=['POST'])
def enter_project_details_post():
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
        flash('Session data missing. Please start over.', 'error')
        return redirect(url_for('create_project'))

    project_details = {
        "clientId": client_id,
        "managerId": manager_id,
        "code": project_code,
        "name": project_name,
        "type": project_type,
        "contractType": contract_type,
        "address": [project_address],  # Assuming `project_address` is a dictionary
        "billingContact": {
            "phone": phone_number,
            "email": email
        }
    }

    result = send_create_project_request(project_details)

    if result:
        flash('Project created successfully!', 'success')
        return redirect(url_for('home'))
    else:
        flash('Failed to create project.', 'error')
        return redirect(url_for('enter_project_details_get'))


@app.route('/create_project/select_employee', methods=['GET'])
def select_employee():
    selected_email = session.get('selected_email')
    employees = get_employees(selected_email)
    
    if employees is None or len(employees) == 0:
        flash("Failed to load employees or no employees found.")
        return redirect(url_for('create_project'))  # Redirect back or to an error page if necessary
    
    return render_template('select_employee.html', employees=employees)


@app.route('/create_project/get_manager_id', methods=['POST'])
def get_manager_id():
    employee_name = request.form.get('employee_name')
    first_name, last_name = employee_name.split()
    
    selected_email = session.get('selected_email')
    manager_id = fetch_manager_id(first_name, last_name, selected_email)

    if manager_id:
        session['manager_id'] = manager_id
        return redirect(url_for('make_project'))
    else:
        flash("No manager found for the selected employee.")
        return redirect(url_for('select_employee'))

@app.route('/create_project/submit', methods=['POST'])
def submit_project():
    project_details = {
        "clientId": session['client_id'],
        "managerId": session['manager_id'],
        "code": request.form.get('project_number'),
        "name": request.form.get('project_name'),
        "type": request.form.get('project_type'),
        "contractType": request.form.get('contract_type'),
        "address": [{
            "street1": request.form.get('street1'),
            "street2": request.form.get('street2'),
            "city": request.form.get('city'),
            "state": request.form.get('state'),
            "zip": request.form.get('zip')
        }],
        "billingContact": {
            "phone": request.form.get('phone_number'),
            "email": request.form.get('email')
        }
    }

    response = send_create_project_request(project_details)
    
    if response.status_code == 201:
        flash("Project created successfully!")
        return redirect(url_for('index'))
    else:
        flash("Failed to create project. Please try again.")
        return redirect(url_for('make_project'))

###############################################
# app routes to export project details
# GET route to display the export project details page
@app.route('/export_project_details', methods=['GET'])
def export_project_details_get():
    # Retrieve project and client data from the session
    project_data = session.get('project_data')
    client_data = session.get('client_data')
    ahj_data = session.get('ahj_data')
    amendment_data = session.get('amendment_data')
    
    # Create Project and Client objects if data exists
    project = Project(**project_data) if project_data else None
    client = Client(**client_data) if client_data else None
    
    return render_template('export_project_details.html', project=project, client=client)

# POST route to handle export project details actions
@app.route('/export_project_details_submit', methods=['POST'])
def export_project_details_post():
    action = request.form.get('action')
    
    if action == 'confirm':
        # Proceed to export the data
        if not session.get('project_data') or not session.get('client_data'):
            flash('Cannot export details. Project or client information is missing.', 'error')
            return redirect(url_for('export_project_details_get'))
        return redirect(url_for('perform_export'))
    
    elif action == 'fetch':
        # Redirect to fetch project details flow
        return redirect(url_for('fetch_user_email_get'))
    
    elif action == 'home':
        # Redirect to home page
        return redirect(url_for('home'))
    
    else:
        flash('Invalid action selected.', 'error')
        return redirect(url_for('export_project_details_get'))


@app.route('/perform_export')
def perform_export():
    # Retrieve data from the session
    project_data = session.get('project_data')
    client_data = session.get('client_data')
    ahj_data = session.get('ahj_data')
    amendment_data = session.get('amendment_data')
    
    if not project_data or not client_data:
        flash('Project and client details are missing. Please fetch them first.')
        return redirect(url_for('fetch_project_email'))
    
    # Create Project and Client objects
    project = Project(**project_data)
    client = Client(**client_data)
    
    # Create Excel workbook for report
    report_workbook = create_workbook()
    report_sheet = report_workbook.active

    # Insert project/client data using models
    insert_project_data(report_sheet, project)
    insert_client_data(report_sheet, client)

    # Insert AHJ & Amendment data if available
    if ahj_data and amendment_data:
        insert_ahj_data(report_sheet, ahj_data, amendment_data)
    
    # Save the workbook
    # For testing, we'll save it locally; in production, adjust the path accordingly
    report_directory = config.REPORT_DIRECTORY
    if not os.path.exists(report_directory):
        os.makedirs(report_directory)
    
    # Construct the file name
    project_code = project.code.replace('/', '_')
    project_name = project.name.replace('/', '_')
    file_name = f"{project_code}_{project_name}.xlsx"
    full_path = os.path.join(report_directory, file_name)
    
    save_result = save_workbook(report_workbook, full_path)
    
    if save_result:
        flash(f"Report created and saved at {full_path}")
    else:
        flash("Failed to save the report.")
    
    return redirect(url_for('home'))

####################################################
# app routes to update project address
# Example of a properly defined route
@app.route('/update_project_address', methods=['GET', 'POST'])
def update_project_address():
    if request.method == 'POST':
        # Logic to update project address
        pass
    return render_template('update_project_address.html')

##########################################
# app routes for creating cover sheet

# New Placeholder Route for Create Cover Sheet
@app.route('/create_cover_sheet', methods=['GET', 'POST'])
def create_cover_sheet():
    """
    Placeholder route for creating a cover sheet.
    Currently displays a 'Coming Soon' page.
    """
    try:
        if request.method == 'POST':
            # Placeholder logic for handling form submission
            flash("Create Cover Sheet feature is under development. Please check back later.", "warning")
            return redirect(url_for('home'))
        
        # Render a placeholder template indicating the feature is under construction
        return render_template('coming_soon.html', feature_name="Create Cover Sheet")
    except Exception as e:
        logger.error(f"Error in create_cover_sheet: {e}")
        return render_template('error.html'), 500


##########################################
# helper functions to get user sub for API calls
def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed

##################################
# app routes to launch application and exit application

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