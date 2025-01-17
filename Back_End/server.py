# Flask imports
from flask import Flask, redirect, request, session, jsonify, render_template, url_for, flash
from flask_session import Session

# General Imports
import logging
import os
import time
from redis import Redis
import requests
import subprocess
import webbrowser

# Module imports
from .auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from .database import setup_database, get_all_emails, get_user_details_by_email
from .token_manager import save_token_data, get_valid_access_token
from .project_manager import get_project_by_code, get_client_by_id
from .models import Project, Client
from .config import get_config
from .ahj_manager import search_ahj_registry, perform_bing_search
from .create_project import get_clients_by_name, get_employees, fetch_manager_id, send_create_project_request
from .export_project_details import create_workbook, insert_project_data, insert_client_data, insert_ahj_data, save_workbook
from .cover_letter import generate_cover_letter

config = get_config()

config.configure_logging()

app = Flask(__name__, static_folder=config.STATIC_FOLDER, template_folder=config.TEMPLATE_FOLDER)

app.config.from_object(config)

app.config['SESSION_REDIS'] = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT
)

# Set up sessions with Redis
Session(app)

# Set up database
DATABASE_PATH = config.DATABASE_PATH
setup_database(DATABASE_PATH)

logger = logging.getLogger(__name__)

##############################################################
# load the home page of application from template

@app.route('/')
def home():
    return render_template('index.html')

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

#####################################################################
# routes to select user's email which is required to retrieve user sub which is required for API calls to CORE
@app.route('/select_user_email_get', methods=['GET'])
def select_user_email_get():
    emails = get_all_emails()  # Retrieve emails from the database
    next_url = request.args.get('next', 'display_project_client_details')
    return render_template('select_user_email.html', emails=emails, next_url=next_url)

@app.route('/select_user_email_post', methods=['POST'])
def select_user_email_post():
    selected_email = request.form.get('email')
    next_url = request.form.get('next_url')
    
    if not selected_email:
        flash('Please select an email.', 'error')
        return redirect(url_for('select_user_email_get'))
    
    # Store the selected email in the session
    session['selected_email'] = selected_email
    flash(f'Email "{selected_email}" selected successfully.', 'success')

    return redirect(url_for('fetch_project_number_get', next=next_url))

#####################################################################
# GET and POST routes to enter a project number and to search a project by number
# GET route to display project number entry form specific to export project details
@app.route('/fetch_project_number', methods=['GET'])
def fetch_project_number_get():
    next_url = request.args.get('next', 'display_project_client_details')
    return render_template('select_project_number.html', next_url=next_url)

# POST route to handle project number submission for export project details
@app.route('/fetch_project_number_submit', methods=['POST'])
def fetch_project_number_post():
    selected_email = session.get('selected_email')
    if not selected_email:
        flash('No email selected. Please select an email first.', 'error')
        return redirect(url_for('select_user_email_get'))
    
    project_number = request.form.get('project_number')
    next_url = request.form.get('next_url')
    
    if not project_number:
        flash('Please enter a project number.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Fetch project details from the backend using selected email and project number
    project_data = get_project_by_code(project_number, selected_email)
    logger.debug(f"project_data in fetch_project_number_submit: {project_data}")
    
    if not project_data:
        flash('Project not found. Please check the Project ID and try again.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Create project and client objects from the retrieved data
    project = Project.from_dict(project_data[0])
    logger.debug(f"project in fetch_project_number_submit: {project}")
    
    client_data = get_client_by_id(project.client_id, selected_email)
    logger.debug(f"client_data in fetch_project_number_submit: {client_data}")
    
    client = Client.from_dict(client_data[0]) if client_data else None
    logger.debug(f"client in fetch_project_number_submit: {client}")
    
    # Store project and client details in the session for use on the details page
    session['project_data'] = {
        'code': project_number,
        'name': project.name,
        'purchase_order_number': project.purchase_order_number,
        'billing_contact': project.billing_contact,
        'street1': project.street1,
        'street2': project.street2,
        'city': project.city,
        'state': project.state,
        'zip_code': project.zip_code
    }
    session['client_data'] = {
        'client_name': client.name,
        'client_email': client.email,
        'client_phone': client.phone,
        'street1': client.street1,
        'street2': client.street2,
        'city': client.city,
        'state': client.state,
        'zip_code': client.zip_code
    }

    # Validate and determine the redirection target
    allowed_routes = ['display_project_client_details', 'display_letter_details_get']
    if next_url not in allowed_routes:
        next_url = 'home'  # Fallback to home if invalid
        
    # Generate the redirection URL
    redirection_url = url_for(next_url)
    
    logger.debug(f"Redirecting to {redirection_url} with project_number: {project_number}")
    
    # Redirect to the display page route
    return redirect(redirection_url)

"""
*************************************************************************************************
"""
"""Unified AHJ Process"""
@app.route('/generate_ahj_report', methods=['POST'])
def generate_ahj_report():
    """
    Consolidated route to generate complete AHJ report including project details,
    AHJ information, and amendments. Maintains compatibility with existing session
    structures and handles missing data gracefully.
    """
    try:
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))
        
        project_number = request.form.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Step 1: Fetch project and client details
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
        
        # Create Project instance using the model's from_dict method
        project = Project.from_dict(project_data[0])
        
        # Validate project address - critical for AHJ search
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address before generating an AHJ report.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Get client data
        client_data = get_client_by_id(project.client_id, selected_email)
        client = Client.from_dict(client_data[0]) if client_data else None

        # Store project data in session - maintaining format for compatibility
        session['project_data'] = {
            'code': project_number,
            'name': project.name,
            'purchase_order_number': project.purchase_order_number,
            'billing_contact': project.billing_contact,
            'street1': project.street1,
            'street2': project.street2,
            'city': project.city,
            'state': project.state,
            'zip_code': project.zip_code
        }
        
        # Store client data in session - maintaining format for compatibility
        session['client_data'] = {
            'client_name': client.name if client else 'N/A',
            'client_email': client.email if client else 'N/A',
            'client_phone': client.phone if client else 'N/A',
            'street1': client.street1 if client else '',
            'street2': client.street2 if client else '',
            'city': client.city if client else '',
            'state': client.state if client else '',
            'zip_code': client.zip_code if client else ''
        }

        # Also store confirmed data for compatibility with other routes
        session['confirmed_project_data'] = session['project_data']
        session['confirmed_client_data'] = session['client_data']

        # Step 2: Search AHJ registry
        project_address = f"{project.street1}, {project.city}, {project.state}, {project.zip_code}"
        ahj_data = search_ahj_registry(project_address)
        
        if not ahj_data:
            flash('AHJ search failed. The report will be generated without AHJ information. You can try searching for AHJ information separately.', 'warning')
            session['stored_ahj_data'] = []
            session['stored_amendment_pdf_links'] = []
            session['stored_amendment_web_links'] = []
            return redirect(url_for('display_report_details_get'))

        # Step 3: Search for amendments if we have AHJ data
        amendments = {"pdf_links": [], "web_links": []}
        try:
            if ahj_data and len(ahj_data) > 0:
                ahj_name = ahj_data[0].get('AHJ Name')
                if ahj_name:
                    query = f"{ahj_name} building code amendments filetype:pdf"
                    pdf_links, web_links = perform_bing_search(query, retries=5)
                    amendments["pdf_links"] = pdf_links
                    amendments["web_links"] = web_links
        except Exception as e:
            logger.error(f"Error searching amendments: {str(e)}")
            flash('Amendment search failed. The report will be generated with AHJ information but without amendments.', 'warning')

        # Store AHJ and amendment data
        session['stored_ahj_data'] = ahj_data
        session['stored_amendment_pdf_links'] = amendments["pdf_links"]
        session['stored_amendment_web_links'] = amendments["web_links"]

        # Success - redirect to display
        flash('Report data generated successfully.', 'success')
        return redirect(url_for('display_report_details_get'))

    except Exception as e:
        logger.error(f"Error generating AHJ report: {str(e)}")
        flash('An error occurred while generating the report. Please try again or generate the report in steps using the individual functions.', 'error')
        return redirect(url_for('home'))

"""
******************************************************************************************************************************
"""
"""End of unified process"""

#############################################################
# app route to confirm project/client details storing them in the session and redirecting the user home
@app.route('/confirm_project_details', methods=['POST'])
def confirm_project_details():
    # Retrieve project and client data from the session
    project_data = session.get('project_data')
    client_data = session.get('client_data')

    if not project_data or not client_data:
        flash("Project or Client data is missing. Please search for a project again.", 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Store confirmed project and client data in session
    session['confirmed_project_data'] = project_data
    session['confirmed_client_data'] = client_data

    flash("Project and Client details confirmed and saved.", 'success')
    return redirect(url_for('home'))

#####################################################
# app routes to search AHJ registry and Bing for amendments to build codes

@app.route('/search_amendments', methods=['POST'])
def search_amendments():
    # Get the AHJ name from the session or address
    ahj_data = session.get('ahj_data')
    
    if not ahj_data:
        flash("No AHJ data found. Please go back and perform a new search.")
        return redirect(url_for('fetch_ahj_address_get'))

    # Get the AHJ name for querying amendments
    ahj_name = ahj_data[0]['AHJ Name'] if ahj_data else session.get('address')

    # Perform Bing search for both PDFs and website links
    query = f"{ahj_name} Building Code Amendments"
    pdf_links, web_links = perform_bing_search(query)

    # Store the amendment links in session for future use
    session['amendment_pdf_links'] = pdf_links
    session['amendment_web_links'] = web_links

    if not pdf_links and not web_links:
        flash("No amendments found.")
        return redirect(url_for('fetch_ahj_address_get'))

    # Render the results to the user
    return render_template('display_amendment_results.html', pdf_links=pdf_links, web_links=web_links)


###############################################################
# app routes to handle exporting the project, client, AHJ, and amendment info fetched by the user to a csv/excel workbook

@app.route('/display_report_details', methods=['GET'])
def display_report_details_get():
    # Retrieve all necessary data from the session
    project = session.get('confirmed_project_data', {})
    logger.debug(f"Project data passed to display_report_details: {project}")
    
    client = session.get('confirmed_client_data', {})
    logger.debug(f"Client data passed to display_report_details: {client}")
    
    ahj_data = session.get('stored_ahj_data', [])
    amendment_pdf_links = session.get('stored_amendment_pdf_links', [])
    amendment_web_links = session.get('stored_amendment_web_links', [])

    return render_template(
        'display_report_details.html',
        project=project,
        client=client,
        ahj_data=ahj_data,
        amendment_pdf_links=amendment_pdf_links,
        amendment_web_links=amendment_web_links
    )

# exports the data and saves it in an excel workbook in the jobs directory
@app.route('/export_report', methods=['POST'])
def export_report_post():
    # Retrieve data from the session
    project_data = session.get('confirmed_project_data')  # updated key
    client_data = session.get('confirmed_client_data')    # updated key
    ahj_data = session.get('stored_ahj_data')
    amendments = {
        "pdf_links": session.get('stored_amendment_pdf_links', []),
        "web_links": session.get('stored_amendment_web_links', [])
    }

    # Verify project_data and client_data are available
    if not project_data or not client_data:
        flash("Missing project or client data. Please confirm details again.", 'error')
        return redirect(url_for('display_report_details_get'))

    # Create workbook and insert data
    workbook = create_workbook()
    sheet = workbook.active
    
    # Debug log for project_data
    logger.debug(f"Project data contents: {project_data}")
    
    insert_project_data(sheet, project_data)
    insert_client_data(sheet, client_data)
    insert_ahj_data(sheet, ahj_data, amendments)

    # Save the workbook and provide feedback
    saved_path = save_workbook(workbook, project_data['code'])  # Use project number or other identifier
    if saved_path:
        flash(f"Workbook successfully saved at {saved_path}", 'success')
        return redirect(url_for('home'))
    else:
        flash("Failed to save workbook. Please try again.", 'error')
        return redirect(url_for('display_report_details_get'))


##########################################
# helper functions to get user sub for API calls
def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed

###################################################################################
# App routes specefic to creating calculation cover letter
####################################################################################

# Get Route to display project / client details to user and allow confirmation
@app.route('/display_letter_details_get', methods=['GET'])
def display_letter_details_get():
    # Retrieve data from session
    project_data = session.get('project_data')
    client_data = session.get('client_data')
    selected_email = session.get('selected_email')

    # Check if all necessary data is present
    if not all([project_data, client_data, selected_email]):
        flash('Missing data. Please start over.', 'error')
        return redirect(url_for('home'))

    # Fetch user's first and last name
    user_details = get_user_details_by_email(selected_email)

    if not user_details:
        flash('User details not found.', 'error')
        return redirect(url_for('home'))

    first_name = user_details.get('first_name')
    last_name = user_details.get('last_name')

    return render_template('display_letter_details.html', 
                           project_data=project_data, 
                           client_data=client_data, 
                           first_name=first_name, 
                           last_name=last_name)
    
# POST route handles confirmation, generates cover letter, and saves it
@app.route('/display_letter_details_post', methods=['POST'])
def display_letter_details_post():
    # Retrieve data from session
    project_data = session.get('project_data')
    client_data = session.get('client_data')
    selected_email = session.get('selected_email')

    # Check if all necessary data is present
    if not all([project_data, client_data, selected_email]):
        flash('Missing data. Please start over.', 'error')
        return redirect(url_for('home'))

    # Fetch user's first and last name
    user_details = get_user_details_by_email(selected_email)

    if not user_details:
        flash('User details not found.', 'error')
        return redirect(url_for('home'))

    first_name = user_details.get('first_name')
    last_name = user_details.get('last_name')

    # Generate the cover letter
    result = generate_cover_letter(project_data, client_data, first_name, last_name)

    if result:
        flash('Cover letter generated successfully.', 'success')
    else:
        flash('Failed to generate cover letter.', 'error')

    return redirect(url_for('home'))


##################################
# app routes to launch application and exit application

# clears all session data for the user and returns them to the home page
# should close app but not working
@app.route('/exit_app')
def exit_app():
    session.clear()  # Clear all session data for the user
    flash("You have been logged out. Session data cleared.")
    return redirect(url_for('home'))


###############################################################
# comented out launch logic and entry point since in production this will be handled by Gunicorn and NGISX
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
    # Launch the Flask app
    app.run(host='127.0.0.1', port=8000, debug=True)
