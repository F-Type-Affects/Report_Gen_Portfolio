# Flask imports
from flask import Flask, redirect, request, session, jsonify, render_template, url_for, flash
from flask_session import Session

# General Imports
import logging
import os
import time
from redis import Redis
import requests
import shutil
import tempfile

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
                    query = f"{ahj_name}, {state} building code amendments filetype:pdf"
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
    Handles both creating new AHJ Reports if needed and updating existing ones.
    Handle both displaying the options form and processing the scraping request.
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

        # Display the options form with project data
        return render_template('select_asce_options.html',
                             project_data=session['project_data'])
    
    try:
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))
        
        # Get project number from session instead of form
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            flash('Please enter a project number.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        project_number = project_data['code']  # Get project number from stored project data

        # Check if AHJ Report exists
        #workbook_exists, result = find_report_workbook(project_number)
        find_result = find_report_workbook(project_number)
        logger.info(f"Raw result from find_report_workbook: {find_result}")
        logger.info(f"Result type: {type(find_result)}")
        
        # Safely unpack the result
        if isinstance(find_result, tuple) and len(find_result) == 2:
            workbook_exists, result = find_result
            logger.info(f"Unpacked values: workbook_exists={workbook_exists} ({type(workbook_exists)}), result={result}")
        else:
            logger.error(f"Unexpected return format from find_report_workbook: {find_result}")
            workbook_exists = False
            result = "Unexpected function return format"

        
        # If workbook doesn't exist, we need to create it first
        if workbook_exists == False:
            logger.info(f"AHJ Report not found for project {project_number}. Creating new report.")
            
            # Get project and client data
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

            # Get client data
            client_data = get_client_by_id(project.client_id, selected_email)
            client = Client.from_dict(client_data[0]) if client_data else None

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

            # Get AHJ data
            project_address = f"{project.street1}, {project.city}, {project.state}, {project.zip_code}"
            ahj_data = search_ahj_registry(project_address)
            
            # Handle amendments
            amendments = {"pdf_links": [], "web_links": []}
            if ahj_data and len(ahj_data) > 0:
                try:
                    ahj_name = ahj_data[0].get('AHJ Name')
                    if ahj_name:
                        query = f"{ahj_name}, {project.state} building code amendments filetype:pdf"
                        amendments["pdf_links"], amendments["web_links"] = perform_bing_search(query, retries=5)
                except Exception as e:
                    logger.error(f"Error searching amendments: {str(e)}")
                    flash('Amendment search failed. Continuing without amendments.', 'warning')

            # Store AHJ data
            session['stored_ahj_data'] = ahj_data or []
            session['stored_amendment_pdf_links'] = amendments["pdf_links"]
            session['stored_amendment_web_links'] = amendments["web_links"]

            # Create and save initial workbook
            workbook = create_workbook()
            insert_project_data(workbook.active, session['project_data'])
            insert_client_data(workbook.active, session['client_data'])
            insert_ahj_data(workbook.active, ahj_data or [], amendments)

            # Save the workbook and get the path
            workbook_path = save_workbook(workbook, project_number)
            if not workbook_path:
                flash('Failed to create AHJ Report. Please verify directory permissions.', 'error')
                logger.error(f"Failed to save workbook for project {project_number}")
                return redirect(url_for('home'))

            # Check that the workbook exists
            if not os.path.exists(workbook_path):
                flash('Workbook was created but file not found. Please check server permissions.', 'error')
                logger.error(f"Workbook file not found after creation: {workbook_path}")
                return redirect(url_for('home'))

            logger.info(f"Successfully created workbook at: {workbook_path}")
        else:
            logger.info(f"Workbook exists check failed. Value: {workbook_exists}, Result: {result}")
        # either work book exist or has been created
        
        # Initialize scraper
        scraper = ASCEScraper()
        
        # Get project address from session
        project_data = session.get('project_data')
        if not project_data:
            flash('Project data not found. Please try again.', 'error')
            return redirect(url_for('home'))
            
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        # Get form data
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            flash('Please select all required ASCE options.', 'error')
            return redirect(url_for('generate_asce_summary'))
        
        # Execute scraping
        success, error_msg, summary_data = scraper.run_scraping_process(
            address=address,
            standard_version=standard_version,
            risk_category=risk_category,
            soil_class=soil_class
        )
        
        if not success:
            flash(f'Failed to scrape ASCE data: {error_msg}', 'error')
            return redirect(url_for('home'))
        
        # Store the summary data in session for the template
        session['summary_data'] = {
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
        
        # Render the display template
        return render_template('display_summary_details.html',
                             project_data=session.get('project_data'),
                             summary_data=summary_data,
                             getattr=getattr)
        
    except Exception as e:
        logger.error(f"Error in generate_asce_summary: {str(e)}")
        flash('An unexpected error occurred. Please try again.', 'error')
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
    App route to generate and download a full ASCE report PDF.
    - GET: Display the options form
    - POST: Process the form and download the report
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

        # Display the options form with project data
        return render_template('select_asce_options.html',
                             project_data=session['project_data'])
    
    # Handle POST request
    try:
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))
        
        # Get project data from session
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            flash('Project data not found. Please try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        project_number = project_data['code']
            
        # Get project address from session
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        # Get form data
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            flash('Please select all required ASCE options.', 'error')
            return redirect(url_for('generate_asce_full_report'))
        
        # Find project directory
        project_dir = find_project_directory(project_number)
        if not project_dir:
            flash(f'Project directory not found for project code: {project_number}', 'error')
            return redirect(url_for('home'))

        # Create the Project_Info directory if it doesn't exist
        project_info_dir = os.path.join(project_dir, "Project_Info")
        if not os.path.exists(project_info_dir):
            os.makedirs(project_info_dir, exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "AHJ_Report"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "ASCE_Hazard_Report"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "USDA_Soil_Reports"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "Archived_AHJ_Reports"), exist_ok=True)
            logger.info(f"Created Project_Info directory structure for project: {project_number}")

        # Use the ASCE_Hazard_Report directory for both pool and non-pool projects
        report_dir = os.path.join(project_info_dir, "ASCE_Hazard_Report")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir, exist_ok=True)
            logger.info(f"Created ASCE_Hazard_Report directory: {report_dir}")
        
        # Create a unique filename with project ID and timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"ASCE_Report_{project_number}_{timestamp}.pdf"
        destination_path = os.path.join(report_dir, filename)
        
        # Initialize the scraper
        scraper = ASCEReportScraper()
        
        try:
            logger.info(f"Starting ASCE report download for project {project_number}")
            
            # Execute scraping
            success, error_msg, temp_path = scraper.run_report_download(
                address=address,
                standard_version=standard_version,
                risk_category=risk_category,
                soil_class=soil_class
            )
            
            if not success:
                flash(f'Failed to download ASCE report: {error_msg}', 'error')
                return redirect(url_for('home'))
                
            try:
                # Verify the directory exists
                if not os.path.exists(report_dir):
                    logger.error(f"Required directory does not exist: {report_dir}")
                    flash(f'The required directory does not exist: {report_dir}. Please contact IT support.', 'error')
                    return redirect(url_for('home'))
        
                # Copy from temp path to final destination
                shutil.copy2(temp_path, destination_path)
                logger.info(f"Report saved to: {destination_path}")
    
                # Clean up the temporary file
                os.remove(temp_path)
    
                flash(f'ASCE report successfully generated and saved to: {destination_path}', 'success')
            except Exception as e:
                logger.error(f"Error saving report: {str(e)}")
                flash('Failed to save the report to the project directory.', 'error')
    
            return redirect(url_for('home'))
            
        finally:
            # Always perform cleanup to ensure resources are released
            scraper.cleanup()
        
    except Exception as e:
        logger.error(f"Error in generate_asce_full_report: {str(e)}")
        flash('An unexpected error occurred. Please try again.', 'error')
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
    App route to generate and download Web Soil Survey reports (Linear Extensibility and Unified Soil Classification).
    - GET: Display confirmation page with project data
    - POST: Process and download the reports
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

        # Display confirmation page with project data
        return render_template('confirm_soil_survey.html',
                             project_data=session['project_data'])
    
    # Handle POST request
    try:
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('select_user_email_get'))
        
        # Get project data from session
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            flash('Project data not found. Please try again.', 'error')
            return redirect(url_for('fetch_project_number_get'))
            
        project_number = project_data['code']
            
        # Get project address from session
        address = f"{project_data['street1']}, {project_data['city']}, {project_data['state']}, {project_data['zip_code']}"
        
        # Find project directory
        project_dir = find_project_directory(project_number)
        if not project_dir:
            flash(f'Project directory not found for project code: {project_number}', 'error')
            return redirect(url_for('home'))

        # Create the Project_Info directory if it doesn't exist
        project_info_dir = os.path.join(project_dir, "Project_Info")
        if not os.path.exists(project_info_dir):
            os.makedirs(project_info_dir, exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "AHJ_Report"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "ASCE_Hazard_Report"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "USDA_Soil_Reports"), exist_ok=True)
            os.makedirs(os.path.join(project_info_dir, "Archived_AHJ_Reports"), exist_ok=True)
            logger.info(f"Created Project_Info directory structure for project: {project_number}")

        # Use the USDA_Soil_Reports directory for the soil survey reports
        report_dir = os.path.join(project_info_dir, "USDA_Soil_Reports")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir, exist_ok=True)
            logger.info(f"Created USDA_Soil_Reports directory: {report_dir}")
        
        # Create timestamp for unique filenames
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        
        # Create unique filenames for the two reports
        linear_filename = f"Linear_Extensibility_{project_number}_{timestamp}.pdf"
        soil_class_filename = f"Unified_Soil_Classification_{project_number}_{timestamp}.pdf"
        
        # Full paths for the destination files
        linear_path = os.path.join(report_dir, linear_filename)
        soil_class_path = os.path.join(report_dir, soil_class_filename)
        
        # Create a custom temporary directory for downloads
        temp_download_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary download directory: {temp_download_dir}")

        # Initialize the scraper with the custom download directory
        config = SoilScraperConfig(download_directory=temp_download_dir, wait_time=90)
        scraper = WebSoilSurveyScraper(config)
        
        # After executing scraping
        success, error_msg, temp_paths = scraper.run_soil_survey(address=address)

        if not success:
            flash(f'Failed to download USDA soil reports: {error_msg}', 'error')
            return redirect(url_for('home'))

        try:
            # Verify the directory exists
            if not os.path.exists(report_dir):
                logger.error(f"Required directory does not exist: {report_dir}")
                flash(f'The required directory does not exist: {report_dir}. Please contact IT support.', 'error')
                return redirect(url_for('home'))

            # Make sure we have at least one PDF
            if not temp_paths:
                flash('No soil reports were downloaded. Please try again.', 'error')
                return redirect(url_for('home'))
        
            # Save downloaded reports based on how many we found
            if len(temp_paths) >= 1:
                # First file - Linear Extensibility
                first_file_path = temp_paths[0]
                logger.info(f"Linear Extensibility Report Path: {first_file_path}")
        
                if os.path.exists(first_file_path) and os.path.getsize(first_file_path) > 0:
                    # Copy from temp path to final destination
                    shutil.copy2(first_file_path, linear_path)
                    logger.info(f"Linear Extensibility report saved to: {linear_path}")
            
                    # Clean up the temporary file
                    try:
                        os.remove(first_file_path)
                    except Exception as e:
                        logger.warning(f"Could not remove temporary file: {str(e)}")
    
            if len(temp_paths) >= 2:
                # Second file - Unified Soil Classification
                second_file_path = temp_paths[1]
                logger.info(f"Unified Soil Classification Report Path: {second_file_path}")
        
                if os.path.exists(second_file_path) and os.path.getsize(second_file_path) > 0:
                 # Copy from temp path to final destination
                    shutil.copy2(second_file_path, soil_class_path)
                    logger.info(f"Unified Soil Classification report saved to: {soil_class_path}")
            
                    # Clean up the temporary file
                    try:
                        os.remove(second_file_path)
                    except Exception as e:
                        logger.warning(f"Could not remove temporary file: {str(e)}")
    
            flash(f'USDA soil reports successfully generated and saved to: {report_dir}', 'success')
            return redirect(url_for('home'))
        
        except Exception as e:
            logger.error(f"Error saving reports: {str(e)}")
            flash('Failed to save the reports to the project directory.', 'error')
            return redirect(url_for('home'))
            
        finally:
            # Always perform cleanup to ensure resources are released
            scraper.cleanup()
            
            # Clean up temp directory
            try:
                shutil.rmtree(temp_download_dir, ignore_errors=True)
                logger.info(f"Removed temporary directory: {temp_download_dir}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in generate_soil_survey: {str(e)}")
        flash('An unexpected error occurred. Please try again.', 'error')
        return redirect(url_for('home'))

"""End of USDA Soil Reports App Route
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
    app.run(host='127.0.0.1', port=8000, debug=True)
