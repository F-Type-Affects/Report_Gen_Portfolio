# Flask imports
from flask import Flask, redirect, request, session, jsonify, render_template, url_for, flash
from flask_session import Session

# General Imports
import logging
import os
import time
from redis import Redis
import requests

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
    Checks if the relevant data is already stored in the session and uses it if it is found
    If the data isn't present it queries it and stores it in the session to be used by this process and so other
    processes can use it.
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

        # Check if we already have the data in session
        project_data = session.get('project_data')
        client_data = session.get('client_data')

        # If no session data, fetch project and client data
        if not project_data or not client_data:
            logger.info("No session data found, fetching project and client data")
            
            # Fetch project details
            project_data = get_project_by_code(project_number, selected_email)
            if not project_data:
                flash('Project not found. Please check the Project ID and try again.', 'error')
                return redirect(url_for('fetch_project_number_get'))

            # Create Project instance
            project = Project.from_dict(project_data[0])

            # Get client data
            client_data = get_client_by_id(project.client_id, selected_email)
            if not client_data:
                flash('Client data not found.', 'error')
                return redirect(url_for('fetch_project_number_get'))

            client = Client.from_dict(client_data[0])

            # Format and store data in session
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

        # Display confirmation page
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
