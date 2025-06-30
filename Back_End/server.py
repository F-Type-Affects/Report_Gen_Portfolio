# Flask imports
from flask import Flask, redirect, request, session, jsonify, render_template, url_for, flash, Response, stream_template
from flask_session import Session
from threading import Thread

# General Imports
import logging
import os
import time
from redis import Redis
import requests
import shutil
import tempfile
import time
import json
import uuid

# Module imports
from .auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from .database import setup_database, get_all_emails, get_user_details_by_email
from .token_manager import save_token_data, get_valid_access_token
from .project_manager import get_project_by_code, get_client_by_id
from .models import Project, Client, ASCESummaryData, WindData, SeismicData, IceData, SnowData
from .config import get_config
from .ahj_manager import search_ahj_registry, perform_bing_search
from .create_project import get_clients_by_name, get_employees, fetch_manager_id, send_create_project_request
from .export_project_details import create_workbook, insert_project_data, insert_client_data, insert_ahj_data, save_workbook, update_workbook_with_summary, find_report_workbook, find_project_directory
from .cover_letter import generate_cover_letter
from .asce_hazard_summary import ASCEScraper
from .asce_hazard_report import ASCEReportScraper
from .soil_scraper import WebSoilSurveyScraper, SoilScraperConfig

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

# Global dictionary to store progress for each session
progress_tracker = {}

# track the progress of generating all the reports at once
# can also track progress of individual reports
class ProgressTracker:
    """Thread-safe progress tracker for long-running operations"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.reset()
    
    def reset(self):
        """Reset progress to initial state"""
        progress_tracker[self.session_id] = {
            'overall_progress': 0,
            'current_step': 0,
            'steps': [
                {'name': 'ASCE Full Report', 'status': 'pending', 'progress': 0},
                {'name': 'Soil Survey', 'status': 'pending', 'progress': 0},
                {'name': 'ASCE Summary', 'status': 'pending', 'progress': 0}
            ],
            'status': 'starting',
            'message': 'Initializing...',
            'error': None,
            'completed': False
        }
    
    def update_step(self, step_index, status, progress=None, message=None):
        """Update a specific step's progress"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        if 0 <= step_index < len(data['steps']):
            data['steps'][step_index]['status'] = status
            if progress is not None:
                data['steps'][step_index]['progress'] = progress
            
            # Update current step
            data['current_step'] = step_index
            
            # Calculate overall progress
            total_progress = sum(step['progress'] for step in data['steps'])
            data['overall_progress'] = total_progress / 3  # 3 steps total
            
            # Update global status and message
            if message:
                data['message'] = message
            
            if status == 'completed':
                # Check if all steps are completed
                if all(step['status'] == 'completed' for step in data['steps']):
                    data['status'] = 'completed'
                    data['completed'] = True
                    data['message'] = 'All reports generated successfully!'
            elif status == 'error':
                data['status'] = 'error'
                data['error'] = message
    
    def set_error(self, error_message):
        """Set error state"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['status'] = 'error'
        data['error'] = error_message
        data['message'] = f'Error: {error_message}'

class SingleStepProgressTracker:
    """Simplified progress tracker for single-step operations"""
    
    def __init__(self, session_id, step_name):
        self.session_id = session_id
        self.step_name = step_name
        self.reset()
    
    def reset(self):
        """Reset progress to initial state"""
        progress_tracker[self.session_id] = {
            'overall_progress': 0,
            'current_step': 0,
            'steps': [
                {'name': self.step_name, 'status': 'pending', 'progress': 0}
            ],
            'status': 'starting',
            'message': 'Initializing...',
            'error': None,
            'completed': False
        }
    
    def update_progress(self, progress, message=None, status='in_progress'):
        """Update progress for the single step"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['steps'][0]['status'] = status
        data['steps'][0]['progress'] = progress
        data['overall_progress'] = progress
        
        if message:
            data['message'] = message
        
        if status == 'completed':
            data['status'] = 'completed'
            data['completed'] = True
            data['message'] = f'{self.step_name} generated successfully!'
        elif status == 'error':
            data['status'] = 'error'
            data['error'] = message
    
    def set_error(self, error_message):
        """Set error state"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['status'] = 'error'
        data['error'] = error_message
        data['message'] = f'Error: {error_message}'
        data['steps'][0]['status'] = 'error'


"""App route to the home page of web application index.html""" 
@app.route('/')
def home():
    return render_template('index.html')

"""End of home route"""

"""
These app routes handle the login and authentication process to the BQE CORE Platform.
This process grants access to the application for the user as well as saves the relevant user information
in a simple SQLite table so they do not need to do this everytime they use the application
"""
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

"""
End of Authentication routes
"""

"""
These routes handle selecting the user email which is used to retrieve the user's sub, acces, and id tokens
and required to query the BQE Core Platforms enbdpoints
"""
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

"""
End of email app routes
"""

"""
App route allows the other app routes to redirect back to the search project number template
"""
@app.route('/fetch_project_number', methods=['GET'])
def fetch_project_number_get():
    next_url = request.args.get('next') 
    return render_template('select_project_number.html', next_url=next_url)

"""
"""

"""
App routes to query to the AHJ registry for IBC codes, query BQE endpoints for project and client data, and
perform bing searches for web links and amendments to the codes provide
Displays the information for user to confirm before exporting
"""
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
                    state = project.state
                    query = f"{ahj_name}, {state} building code amendments"
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

"""End of unified process"""

"""App routes to display AHJ report details and to export the reports to the appropriate project directory"""
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

"""App route to generate cover letter.
   Allows for all process be to be done in any order
"""

@app.route('/generate_cover_letter', methods=['POST'])
def generate_cover_letter_route():
    """
    Handles cover letter generation requests. For each request, it:
    1. Validates the user session and input
    2. Fetches fresh project and client data for the requested project number
    3. Updates the session with the new data
    4. Displays the confirmation page with current project details
    """
    try:
        # Validate user session
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))

        # Get and validate project number from form
        project_number = request.form.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Always fetch fresh project data for the requested project number
        logger.info(f"Fetching data for project number: {project_number}")
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Create Project instance and fetch related client data
        project = Project.from_dict(project_data[0])
        client_data = get_client_by_id(project.client_id, selected_email)
        if not client_data:
            flash('Client data not found.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        client = Client.from_dict(client_data[0])

        # Update session with new project and client data
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

        # Get user details for display
        user_details = get_user_details_by_email(selected_email)
        if not user_details:
            flash('User details not found.', 'error')
            return redirect(url_for('home'))

        # Add debug logging to verify session data
        logger.info(f"Updated session with project number: {session['project_data']['code']}")

        # Display confirmation page with current data
        return render_template('display_letter_details.html',
                             project_data=session['project_data'],
                             client_data=session['client_data'],
                             first_name=user_details.get('first_name'),
                             last_name=user_details.get('last_name'))

    except Exception as e:
        logger.error(f"Error preparing cover letter data: {str(e)}")
        flash('An error occurred while preparing the cover letter. Please try again.', 'error')
        return redirect(url_for('home'))

@app.route('/generate_cover_letter_confirmed', methods=['POST'])
def generate_cover_letter_confirmed():
    """
    Second route to handle actual cover letter generation after confirmation.
    """
    try:
        selected_email = session.get('selected_email')
        user_details = get_user_details_by_email(selected_email)
        
        result = generate_cover_letter(
            session['project_data'],
            session['client_data'],
            user_details.get('first_name'),
            user_details.get('last_name')
        )

        if result:
            flash('Cover letter generated successfully.', 'success')
        else:
            flash('Failed to generate cover letter.', 'error')

        return redirect(url_for('home'))

    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        flash('An error occurred while generating the cover letter. Please try again.', 'error')
        return redirect(url_for('home'))

"""End of Cover Letter specefic app route
"""

"""
App routes to scrape ASCE hazard tool for summary table and Full Report
"""
"""
This app route handles scraping the ASCE site for the summary table
"""
@app.route('/generate_asce_summary', methods=['GET', 'POST'])
def generate_asce_summary():
    """
    App route to generate ASCE Hazard Tool summary and add it to the AHJ Report.
    Updated to use background threading with progress tracking for consistency.
    """
    if request.method == 'GET':
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        # Get project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
        
        # Create Project instance
        project = Project.from_dict(project_data[0])
        
        # Validate project address
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Store data in session
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

        # Use the shared ASCE template
        return render_template('asce_individual_options.html',
                             project_data=session['project_data'])
    
    # Handle POST request with background threading
    try:
        # Generate unique session ID for this operation
        session_id = str(uuid.uuid4())
        session['progress_session_id'] = session_id
        
        # Initialize single-step progress tracker
        tracker = SingleStepProgressTracker(session_id, 'ASCE Summary')
        
        # Validate request
        validation_result = _validate_individual_asce_request()
        if validation_result['error']:
            tracker.set_error(validation_result['message'])
            flash(validation_result['message'], 'error')
            return redirect(validation_result['redirect'])
        
        # Start background task for ASCE Summary
        thread = Thread(
            target=_execute_individual_asce_summary_with_progress,
            args=(
                session_id,
                validation_result['project_data'],
                validation_result['address'],
                validation_result['asce_options']
            )
        )
        thread.daemon = True
        thread.start()
        
        # Return page with progress tracking
        return render_template('asce_individual_options.html',
                             project_data=validation_result['project_data'],
                             progress_session_id=session_id,
                             show_progress=True)
        
    except Exception as e:
        logger.error(f"Critical error in generate_asce_summary: {str(e)}")
        flash('A critical error occurred during summary generation.', 'error')
        return redirect(url_for('home'))


def _execute_individual_asce_summary_with_progress(session_id, project_data, address, asce_options):
    """
    Execute individual ASCE Summary with progress tracking.
    Note: This runs in a background thread without Flask request context.
    """
    tracker = SingleStepProgressTracker(session_id, 'ASCE Summary')
    project_number = project_data['code']
    
    try:
        # Step 1: Check if AHJ Report exists
        tracker.update_progress(10, 'Checking AHJ report availability...')
        
        find_result = find_report_workbook(project_number)
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
        else:
            workbook_exists = False
            result = "Unexpected function return format"
        
        # If workbook doesn't exist, create it first
        if not workbook_exists:
            logger.info(f"AHJ Report not found for project {project_number}. Creating new report.")
            tracker.update_progress(20, 'Creating AHJ report...')
            
            # Create a minimal workbook to hold the ASCE summary
            workbook = create_workbook()
            insert_project_data(workbook.active, project_data)
            
            # Create minimal client data if not available
            client_data = {
                'client_name': 'N/A',
                'client_email': 'N/A', 
                'client_phone': 'N/A',
                'street1': '',
                'street2': '',
                'city': '',
                'state': '',
                'zip_code': ''
            }
            insert_client_data(workbook.active, client_data)
            
            # Save the workbook
            workbook_path = save_workbook(workbook, project_number)
            if not workbook_path:
                tracker.set_error('Failed to create AHJ Report for ASCE Summary')
                return
                
            logger.info(f"Created minimal AHJ report for ASCE Summary at: {workbook_path}")
        
        # Step 2: Initialize ASCE scraper
        tracker.update_progress(40, 'Initializing ASCE summary scraper...')
        scraper = ASCEScraper()
        
        try:
            # Step 3: Execute scraping
            tracker.update_progress(60, 'Extracting ASCE summary data...')
            
            success, error_msg, summary_data = scraper.run_scraping_process(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                tracker.set_error(f'Failed to extract ASCE summary: {error_msg}')
                return
            
            # Step 4: Save summary to workbook
            tracker.update_progress(80, 'Saving summary to AHJ report...')
            
            success, result = update_workbook_with_summary(project_number, summary_data)
            if not success:
                tracker.set_error(f'Failed to save summary to workbook: {result}')
                return
            
            # Step 5: Store summary data globally for later retrieval
            tracker.update_progress(90, 'Preparing summary display...')
            
            # Store summary data in Redis or global progress tracker for retrieval
            # Since we can't access Flask session from background thread
            summary_dict = {
                'wind_data': {
                    'wind_speed': summary_data.wind_data.wind_speed,
                    'ten_year_mri': summary_data.wind_data.ten_year_mri,
                    'twenty_five_year_mri': summary_data.wind_data.twenty_five_year_mri,
                    'fifty_year_mri': summary_data.wind_data.fifty_year_mri,
                    'hundred_year_mri': summary_data.wind_data.hundred_year_mri,
                    'unit': summary_data.wind_data.unit
                },
                'seismic_data': vars(summary_data.seismic_data),
                'ice_data': vars(summary_data.ice_data),
                'snow_data': vars(summary_data.snow_data)
            }
            
            # Store in the progress tracker for retrieval by the display route
            if session_id in progress_tracker:
                progress_tracker[session_id]['summary_data'] = summary_dict
                progress_tracker[session_id]['project_data'] = project_data
            
            # Mark as completed
            tracker.update_progress(100, 'ASCE Summary completed successfully!', 'completed')
            
            logger.info(f"ASCE Summary generation completed successfully for project {project_number}")
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in individual ASCE summary generation: {str(e)}")
        tracker.set_error(str(e))


@app.route('/display_asce_summary_results')
def display_asce_summary_results():
    """
    Route to display ASCE summary results after background processing is complete.
    This retrieves data from the progress tracker since we can't use session from background threads.
    """
    try:
        # Get the progress session ID
        progress_session_id = session.get('progress_session_id')
        if not progress_session_id or progress_session_id not in progress_tracker:
            flash('Summary data not found. Please try generating the summary again.', 'error')
            return redirect(url_for('home'))
        
        # Retrieve data from progress tracker
        tracker_data = progress_tracker[progress_session_id]
        summary_dict = tracker_data.get('summary_data')
        project_data = tracker_data.get('project_data')
        
        if not project_data or not summary_dict:
            flash('Summary data incomplete. Please try generating the summary again.', 'error')
            return redirect(url_for('home'))
        
        # Store in session for the template (now we're back in request context)
        session['project_data'] = project_data
        session['summary_data'] = summary_dict
        
        # Reconstruct the summary data objects for the template
        summary_data = ASCESummaryData(
            wind_data=WindData(**summary_dict['wind_data']),
            seismic_data=SeismicData(**summary_dict['seismic_data']),
            ice_data=IceData(**summary_dict['ice_data']),
            snow_data=SnowData(**summary_dict['snow_data'])
        )
        
        # Clean up progress tracker entry (optional)
        try:
            del progress_tracker[progress_session_id]
        except KeyError:
            pass  # Already cleaned up
        
        # Render the display template
        return render_template('display_summary_details.html',
                             project_data=project_data,
                             summary_data=summary_data,
                             getattr=getattr)
        
    except Exception as e:
        logger.error(f"Error displaying ASCE summary results: {str(e)}")
        flash('An error occurred while displaying the summary results.', 'error')
        return redirect(url_for('home'))
 
"""
This app route saves the extracted summary table to the AHJ report workbook after the results are displayed to the user
"""
@app.route('/save_summary_report', methods=['POST'])
def save_summary_report():
    try:
        project_number = session.get('project_data', {}).get('code')
        summary_dict = session.get('summary_data')
        
        if not project_number or not summary_dict:
            flash('Missing required data. Please try again.', 'error')
            return redirect(url_for('home'))
            
        # Reconstruct the class instances
        summary_data = ASCESummaryData(
            wind_data=WindData(**summary_dict['wind_data']),
            seismic_data=SeismicData(**summary_dict['seismic_data']),
            ice_data=IceData(**summary_dict['ice_data']),
            snow_data=SnowData(**summary_dict['snow_data'])
        )
            
        success, result = update_workbook_with_summary(project_number, summary_data)
        
        if success:
            flash('ASCE Summary data successfully saved to report.', 'success')
        else:
            flash(f'Failed to save summary data: {result}', 'error')
            
        return redirect(url_for('home'))
        
    except Exception as e:
        logger.error(f"Error saving summary report: {str(e)}")
        flash('An unexpected error occurred while saving the report.', 'error')
        return redirect(url_for('home'))

"""
This app route handles scraping the ASCE website for the the full report and saves it to the appropriate project sub directory
"""
@app.route('/generate_asce_full_report', methods=['GET', 'POST'])
def generate_asce_full_report():
    """
    Updated ASCE Full Report route with progress tracking
    """
    if request.method == 'GET':
        # Existing GET logic (display form)
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        # Get and validate project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
        
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Store data in session
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

        return render_template('asce_individual_options.html',
                             project_data=session['project_data'])
    
    # Handle POST request with progress tracking
    try:
        # Generate unique session ID for this operation
        session_id = str(uuid.uuid4())
        session['progress_session_id'] = session_id
        
        # Initialize single-step progress tracker
        tracker = SingleStepProgressTracker(session_id, 'ASCE Full Report')
        
        # Validate request
        validation_result = _validate_individual_asce_request()
        if validation_result['error']:
            tracker.set_error(validation_result['message'])
            flash(validation_result['message'], 'error')
            return redirect(validation_result['redirect'])
        
        # Start background task
        thread = Thread(
            target=_execute_individual_asce_report_with_progress,
            args=(
                session_id,
                validation_result['project_data'],
                validation_result['address'],
                validation_result['asce_options']
            )
        )
        thread.daemon = True
        thread.start()
        
        # Return page with progress tracking
        return render_template('asce_individual_options.html',
                             project_data=validation_result['project_data'],
                             progress_session_id=session_id,
                             show_progress=True)
        
    except Exception as e:
        logger.error(f"Critical error in generate_asce_full_report: {str(e)}")
        flash('A critical error occurred during report generation.', 'error')
        return redirect(url_for('home'))
"""
End of ASCE web scraping app routes
"""

"""
App route to handle scraping and downloading both USDA Soil Reports:
    - Linear Extensability
    - Unified Soil Classification
"""
@app.route('/generate_soil_survey', methods=['GET', 'POST'])
def generate_soil_survey():
    """
    Updated Soil Survey route with progress tracking
    """
    if request.method == 'GET':
        # Existing GET logic (your current implementation)
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        # Get and validate project data (your existing logic)
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
        
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('fetch_project_number_get'))

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

        return render_template('confirm_soil_survey.html',
                             project_data=session['project_data'])
    
    # Handle POST request with progress tracking
    try:
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        session['progress_session_id'] = session_id
        
        # Initialize single-step progress tracker
        tracker = SingleStepProgressTracker(session_id, 'USDA Soil Survey')
        
        # Validate request
        validation_result = _validate_individual_soil_request()
        if validation_result['error']:
            tracker.set_error(validation_result['message'])
            flash(validation_result['message'], 'error')
            return redirect(validation_result['redirect'])
        
        # Start background task
        thread = Thread(
            target=_execute_individual_soil_survey_with_progress,
            args=(
                session_id,
                validation_result['project_data'],
                validation_result['address']
            )
        )
        thread.daemon = True
        thread.start()
        
        # Return page with progress tracking
        return render_template('confirm_soil_survey.html',
                             project_data=validation_result['project_data'],
                             progress_session_id=session_id,
                             show_progress=True)
        
    except Exception as e:
        logger.error(f"Critical error in generate_soil_survey: {str(e)}")
        flash('A critical error occurred during report generation.', 'error')
        return redirect(url_for('home'))

"""
End of USDA Soil Reports App Route
"""

# ==============================================================================
# INDIVIDUAL EXECUTION FUNCTIONS WITH PROGRESS
# ==============================================================================

def _execute_individual_asce_report_with_progress(session_id, project_data, address, asce_options):
    """Execute individual ASCE report with progress tracking - FIXED"""
    tracker = SingleStepProgressTracker(session_id, 'ASCE Full Report')
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        tracker.update_progress(10, 'Setting up project directories...')
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        # Execute ASCE report generation
        tracker.update_progress(30, 'Starting ASCE report generation...')
        result = _execute_asce_full_report_with_progress(
            project_number, address, asce_options, project_dir, tracker, 0
        )
        
        if result['success']:
            tracker.update_progress(100, 'ASCE Full Report completed successfully!', 'completed')
        else:
            tracker.set_error(result['message'])
            
    except Exception as e:
        logger.error(f"Error in individual ASCE report generation: {str(e)}")
        tracker.set_error(str(e))

def _execute_individual_soil_survey_with_progress(session_id, project_data, address):
    """Execute individual soil survey with progress tracking - FIXED"""
    tracker = SingleStepProgressTracker(session_id, 'USDA Soil Survey')
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        tracker.update_progress(10, 'Setting up project directories...')
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        # Execute soil survey generation
        tracker.update_progress(30, 'Starting soil survey generation...')
        result = _execute_soil_survey_with_progress(
            project_number, address, project_dir, tracker, 0
        )
        
        if result['success']:
            tracker.update_progress(100, f'Generated {len(result["paths"])} soil reports successfully!', 'completed')
        else:
            tracker.set_error(result['message'])
            
    except Exception as e:
        logger.error(f"Error in individual soil survey generation: {str(e)}")
        tracker.set_error(str(e))

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

def _validate_individual_asce_request():
    """Validate ASCE individual request"""
    try:
        selected_email = session.get('selected_email')
        if not selected_email:
            return {
                'error': True,
                'message': 'No email selected. Please select an email first.',
                'redirect': url_for('select_user_email_get')
            }
        
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('fetch_project_number_get')
            }
        
        # Get ASCE form options from request
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            return {
                'error': True,
                'message': 'Please select all required ASCE options.',
                'redirect': url_for('generate_asce_full_report')
            }
        
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        return {
            'error': False,
            'project_data': project_data,
            'address': address,
            'asce_options': {
                'standard_version': standard_version,
                'risk_category': risk_category,
                'soil_class': soil_class
            }
        }
        
    except Exception as e:
        logger.error(f"Error in _validate_individual_asce_request: {str(e)}")
        return {
            'error': True,
            'message': 'Validation error occurred. Please try again.',
            'redirect': url_for('home')
        }

def _validate_individual_soil_request():
    """Validate soil survey individual request"""
    try:
        selected_email = session.get('selected_email')
        if not selected_email:
            return {
                'error': True,
                'message': 'No email selected. Please select an email first.',
                'redirect': url_for('select_user_email_get')
            }
        
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('fetch_project_number_get')
            }
        
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        return {
            'error': False,
            'project_data': project_data,
            'address': address
        }
        
    except Exception as e:
        logger.error(f"Error in _validate_individual_soil_request: {str(e)}")
        return {
            'error': True,
            'message': 'Validation error occurred. Please try again.',
            'redirect': url_for('home')
        }

"""
App route to run all web scraping processes at once
"""
"""
Unified app route to generate all three web scraping reports in sequence:
1. ASCE Full Report PDF
2. USDA Soil Reports (Linear Extensibility & Unified Soil Classification)
3. ASCE Summary Table (saved to AHJ Report)

PREREQUISITE: AHJ Report must exist for the project before running this route.
"""
@app.route('/generate_all_reports', methods=['GET', 'POST'])
def generate_all_reports():
    """
    Updated route with real progress tracking
    """
    if request.method == 'GET':
        return _handle_get_request_unified()
    
    try:
        # Generate unique session ID for this operation
        session_id = str(uuid.uuid4())
        session['progress_session_id'] = session_id
        
        # Initialize progress tracker
        tracker = ProgressTracker(session_id)
        
        # Validate request (your existing validation)
        validation_result = _validate_unified_request()
        if validation_result['error']:
            tracker.set_error(validation_result['message'])
            flash(validation_result['message'], 'error')
            return redirect(validation_result['redirect'])
        
        # Start background task
        thread = Thread(
            target=_execute_unified_scraping_with_progress,
            args=(
                session_id,
                validation_result['project_data'],
                validation_result['address'],
                validation_result['asce_options']
            )
        )
        thread.daemon = True
        thread.start()
        
        # Return page with progress tracking
        return render_template('unified_reports_config.html',
                             project_data=validation_result['project_data'],
                             progress_session_id=session_id,
                             show_progress=True)
        
    except Exception as e:
        logger.error(f"Critical error in generate_all_reports: {str(e)}")
        flash('A critical error occurred during report generation.', 'error')
        return redirect(url_for('home'))

def _execute_unified_scraping_with_progress(session_id, project_data, address, asce_options):
    """
    Execute all scraping operations with real progress tracking
    """
    tracker = ProgressTracker(session_id)
    project_number = project_data['code']
    
    try:
        # Ensure project directory exists
        project_dir = _ensure_project_directory_structure(project_number)
        if not project_dir:
            tracker.set_error(f'Failed to create/access project directory for {project_number}')
            return
        
        logger.info(f"Starting unified scraping for project {project_number} (Session: {session_id})")
        
        # Step 1: ASCE Full Report PDF
        tracker.update_step(0, 'in_progress', 0, 'Starting ASCE Full Report generation...')
        result_1 = _execute_asce_full_report_with_progress(
            project_number, address, asce_options, project_dir, tracker, 0
        )
        
        if not result_1['success']:
            tracker.set_error(f"ASCE Full Report failed: {result_1['message']}")
            return
        
        tracker.update_step(0, 'completed', 100, 'ASCE Full Report completed successfully')
        
        # Step 2: USDA Soil Survey Reports
        tracker.update_step(1, 'in_progress', 0, 'Starting USDA Soil Survey generation...')
        result_2 = _execute_soil_survey_with_progress(
            project_number, address, project_dir, tracker, 1
        )
        
        if not result_2['success']:
            tracker.set_error(f"Soil Survey failed: {result_2['message']}")
            return
            
        tracker.update_step(1, 'completed', 100, 'Soil Survey reports completed successfully')
        
        # Step 3: ASCE Summary Table
        tracker.update_step(2, 'in_progress', 0, 'Starting ASCE Summary generation...')
        result_3 = _execute_asce_summary_with_progress(
            project_number, address, asce_options, tracker, 2
        )
        
        if not result_3['success']:
            tracker.set_error(f"ASCE Summary failed: {result_3['message']}")
            return
            
        tracker.update_step(2, 'completed', 100, 'ASCE Summary completed successfully')
        
        logger.info(f"Completed unified scraping for project {project_number}")
        
    except Exception as e:
        logger.error(f"Error in unified scraping sequence: {str(e)}")
        tracker.set_error(f"Unexpected error: {str(e)}")

def _execute_asce_full_report_with_progress(project_number, address, asce_options, project_dir, tracker, step_index):
    """Execute ASCE Full Report with progress updates - FIXED for SingleStepProgressTracker"""
    try:
        # Set up file paths
        report_dir = os.path.join(project_dir, "Project_Info", "ASCE_Hazard_Report")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"ASCE_Report_{project_number}_{timestamp}.pdf"
        destination_path = os.path.join(report_dir, filename)
        
        # Initialize scraper
        if isinstance(tracker, SingleStepProgressTracker):
            # For individual reports - use update_progress method
            tracker.update_progress(10, 'Initializing ASCE scraper...')
        else:
            # For unified reports - use update_step method
            tracker.update_step(step_index, 'in_progress', 10, 'Initializing ASCE scraper...')
        
        scraper = ASCEReportScraper()
        
        try:
            # Update progress during scraping
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(30, 'Accessing ASCE website...')
            else:
                tracker.update_step(step_index, 'in_progress', 30, 'Accessing ASCE website...')
            
            # Execute scraping with progress callbacks
            success, error_msg, temp_path = scraper.run_report_download(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                return {'success': False, 'message': error_msg, 'path': None}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Saving ASCE report...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Saving ASCE report...')
            
            # Copy to final destination
            shutil.copy2(temp_path, destination_path)
            os.remove(temp_path)
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, 'ASCE report saved successfully')
            else:
                tracker.update_step(step_index, 'in_progress', 95, 'ASCE report saved successfully')
            
            logger.info(f"ASCE Full Report saved to: {destination_path}")
            return {
                'success': True,
                'message': 'ASCE Full Report generated successfully',
                'path': destination_path
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_asce_full_report_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'path': None}

def _execute_soil_survey_with_progress(project_number, address, project_dir, tracker, step_index):
    """Execute Soil Survey with progress updates - FIXED for SingleStepProgressTracker"""
    temp_download_dir = None
    
    try:
        # Set up directories
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(10, 'Setting up soil survey directories...')
        else:
            tracker.update_step(step_index, 'in_progress', 10, 'Setting up soil survey directories...')
            
        report_dir = os.path.join(project_dir, "Project_Info", "USDA_Soil_Reports")
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Create file paths
        linear_filename = f"Linear_Extensibility_{project_number}_{timestamp}.pdf"
        soil_class_filename = f"Unified_Soil_Classification_{project_number}_{timestamp}.pdf"
        
        linear_path = os.path.join(report_dir, linear_filename)
        soil_class_path = os.path.join(report_dir, soil_class_filename)
        
        # Create temporary directory
        temp_download_dir = tempfile.mkdtemp()
        
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(20, 'Initializing soil survey scraper...')
        else:
            tracker.update_step(step_index, 'in_progress', 20, 'Initializing soil survey scraper...')
        
        # Initialize scraper
        config = SoilScraperConfig(download_directory=temp_download_dir, wait_time=90)
        scraper = WebSoilSurveyScraper(config)
        
        try:
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(40, 'Accessing USDA soil survey website...')
            else:
                tracker.update_step(step_index, 'in_progress', 40, 'Accessing USDA soil survey website...')
            
            # Execute scraping
            success, error_msg, temp_paths = scraper.run_soil_survey(address=address)
            
            if not success:
                return {'success': False, 'message': error_msg, 'paths': []}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Processing soil survey reports...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Processing soil survey reports...')
            
            # Process downloaded files
            saved_paths = []
            
            if len(temp_paths) >= 1 and os.path.exists(temp_paths[0]):
                shutil.copy2(temp_paths[0], linear_path)
                saved_paths.append(linear_path)
                
            if len(temp_paths) >= 2 and os.path.exists(temp_paths[1]):
                shutil.copy2(temp_paths[1], soil_class_path)
                saved_paths.append(soil_class_path)
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, f'Saved {len(saved_paths)} soil reports')
            else:
                tracker.update_step(step_index, 'in_progress', 95, f'Saved {len(saved_paths)} soil reports')
            
            return {
                'success': True,
                'message': f'Generated {len(saved_paths)} soil reports successfully',
                'paths': saved_paths
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_soil_survey_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'paths': []}
    finally:
        # Clean up temporary directory
        if temp_download_dir:
            try:
                shutil.rmtree(temp_download_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory: {str(e)}")

def _execute_asce_summary_with_progress(project_number, address, asce_options, tracker, step_index):
    """Execute ASCE Summary with progress updates - FIXED for SingleStepProgressTracker"""
    try:
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(10, 'Checking AHJ report availability...')
        else:
            tracker.update_step(step_index, 'in_progress', 10, 'Checking AHJ report availability...')
        
        # Check if AHJ Report exists
        find_result = find_report_workbook(project_number)
        
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
        else:
            workbook_exists = False
        
        if not workbook_exists:
            return {
                'success': False,
                'message': f'AHJ Report not found for project {project_number}',
                'data': None
            }
        
        if isinstance(tracker, SingleStepProgressTracker):
            tracker.update_progress(30, 'Initializing ASCE summary scraper...')
        else:
            tracker.update_step(step_index, 'in_progress', 30, 'Initializing ASCE summary scraper...')
        
        # Initialize scraper
        scraper = ASCEScraper()
        
        try:
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(50, 'Extracting ASCE summary data...')
            else:
                tracker.update_step(step_index, 'in_progress', 50, 'Extracting ASCE summary data...')
            
            # Execute scraping
            success, error_msg, summary_data = scraper.run_scraping_process(
                address=address,
                standard_version=asce_options['standard_version'],
                risk_category=asce_options['risk_category'],
                soil_class=asce_options['soil_class']
            )
            
            if not success:
                return {'success': False, 'message': error_msg, 'data': None}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(80, 'Saving summary to AHJ report...')
            else:
                tracker.update_step(step_index, 'in_progress', 80, 'Saving summary to AHJ report...')
            
            # Save to AHJ report
            success, result = update_workbook_with_summary(project_number, summary_data)
            
            if not success:
                return {'success': False, 'message': f'Failed to save summary: {result}', 'data': summary_data}
            
            if isinstance(tracker, SingleStepProgressTracker):
                tracker.update_progress(95, 'ASCE summary saved to AHJ report')
            else:
                tracker.update_step(step_index, 'in_progress', 95, 'ASCE summary saved to AHJ report')
            
            return {
                'success': True,
                'message': 'ASCE Summary generated and saved',
                'data': summary_data
            }
            
        finally:
            scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Error in _execute_asce_summary_with_progress: {str(e)}")
        return {'success': False, 'message': str(e), 'data': None}


@app.route('/progress/<session_id>')
def progress_stream(session_id):
    """
    Server-Sent Events endpoint for real-time progress updates
    """
    def generate_progress():
        """Generator function for SSE stream"""
        while True:
            if session_id in progress_tracker:
                data = progress_tracker[session_id]
                yield f"data: {json.dumps(data)}\n\n"
                
                # Stop streaming if completed or error
                if data.get('completed') or data.get('status') == 'error':
                    break
            else:
                # No progress data available
                yield f"data: {json.dumps({'status': 'no_data'})}\n\n"
            
            time.sleep(1)  # Update every second
    
    return Response(
        generate_progress(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )

def _handle_get_request_unified():
    """
    Handle GET request for unified report generation.
    Now uses the dedicated unified_reports_config.html template.
    """
    try:
        # Validate user session
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))

        # Get and validate project number
        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        # Fetch and validate project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
        
        # Create Project instance and validate address
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. All web scraping reports require a complete address.', 'error')
            return redirect(url_for('fetch_project_number_get'))

        # Store project data in session
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

        # Use the new dedicated template for unified reports
        return render_template('unified_reports_config.html',
                             project_data=session['project_data'])
        
    except Exception as e:
        logger.error(f"Error in _handle_get_request_unified: {str(e)}")
        flash('An error occurred while preparing the report generation form.', 'error')
        return redirect(url_for('home'))


def _validate_unified_request():
    """
    Validate all required data for unified report generation.
    
    Returns:
        dict: Validation result with error status, message, redirect, and data
    """
    try:
        # Validate user session
        selected_email = session.get('selected_email')
        if not selected_email:
            return {
                'error': True,
                'message': 'No email selected. Please select an email first.',
                'redirect': url_for('select_user_email_get')
            }
        
        # Validate project data in session
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('fetch_project_number_get')
            }
        
        # Check if AHJ Report exists - REQUIRED for web scraping reports
        project_number = project_data['code']
        find_result = find_report_workbook(project_number)
        
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
        else:
            logger.error(f"Unexpected return format from find_report_workbook: {find_result}")
            workbook_exists = False
            result = "Could not verify AHJ report status"
        
        if not workbook_exists:
            return {
                'error': True,
                'message': f'AHJ Report not found for project {project_number}. Please generate the AHJ Report first before running web scraping reports.',
                'redirect': url_for('fetch_project_number_get')
            }
        
        # Validate ASCE form options
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            return {
                'error': True,
                'message': 'Please select all required ASCE options.',
                'redirect': url_for('generate_all_reports')
            }
        
        # Construct address string
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        return {
            'error': False,
            'project_data': project_data,
            'address': address,
            'asce_options': {
                'standard_version': standard_version,
                'risk_category': risk_category,
                'soil_class': soil_class
            }
        }
        
    except Exception as e:
        logger.error(f"Error in _validate_unified_request: {str(e)}")
        return {
            'error': True,
            'message': 'Validation error occurred. Please try again.',
            'redirect': url_for('home')
        }


def _ensure_project_directory_structure(project_number):
    """
    Ensure all required project directories exist.
    
    Args:
        project_number (str): The project number/code
        
    Returns:
        str: Project directory path if successful, None if failed
    """
    try:
        # Find the main project directory
        project_dir = find_project_directory(project_number)
        if not project_dir:
            logger.error(f'Project directory not found for project code: {project_number}')
            return None

        # Create the Project_Info directory structure if it doesn't exist
        project_info_dir = os.path.join(project_dir, "Project_Info")
        
        # Define all required subdirectories
        required_dirs = [
            project_info_dir,
            os.path.join(project_info_dir, "AHJ_Report"),
            os.path.join(project_info_dir, "ASCE_Hazard_Report"),
            os.path.join(project_info_dir, "USDA_Soil_Reports"),
            os.path.join(project_info_dir, "Archived_AHJ_Reports")
        ]
        
        # Create all directories
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logger.info(f"Created directory: {dir_path}")
        
        logger.info(f"Project directory structure verified/created for project: {project_number}")
        return project_dir
        
    except Exception as e:
        logger.error(f"Error creating project directory structure: {str(e)}")
        return None


"""
End of app route that runs all web scrapers at once
"""


"""Helper functions to get specefic user data for calls to endpoints"""
def login_user(sub):
    session['user_sub'] = sub  # Store the sub in session after successful login

def get_user_sub():
    return session.get('user_sub')  # Retrieve the sub when needed


# clears all session data for the user and returns them to the home page
@app.route('/exit_app')
def exit_app():
    session.clear()  # Clear all session data for the user
    flash("You have been logged out. Session data cleared.")
    return redirect(url_for('home'))


# entry point
if __name__ == '__main__':
    # Launch the Flask app
    app.run(host='127.0.0.1', port=8888, debug=True)
