import logging
import os
import time
from flask import Flask, redirect, request, session, jsonify, render_template, url_for, flash
from flask_session import Session
from redis import Redis
from datetime import timedelta

from .auth import get_authorization_url, exchange_code_for_token, decode_id_token, get_user_info
from .database import setup_database, get_all_emails
from .token_manager import save_token_data, get_valid_access_token
from .project_manager import get_project_by_code, get_client_by_id
from .models import Project, Client
from . import config
from .ahj_manager import search_ahj_registry, perform_bing_search
from .create_project import get_clients_by_name, get_employees, fetch_manager_id, send_create_project_request
from .export_project_details import create_workbook, insert_project_data, insert_client_data, insert_ahj_data, save_workbook

app = Flask(
	__name__,
	static_folder="/home/frank/SML_Reports_Test/SML_Report_Gen/Front_End_Web/static",
	template_folder="/home/frank/SML_Reports_Test/SML_Report_Gen/Front_End_Web/templates"
)

# app configuration
app.config['DEBUG'] = False  # Ensure debugging is off for production
app.config['SECRET_KEY'] = config.APP_KEY  # Securely generate and store this
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False  # Set to False so the session expires when the user closes the app
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_USE_SIGNER'] = True  # Encrypt session cookies for extra security
app.config['SESSION_KEY_PREFIX'] = 'sml_report_gen:'  # Optional prefix to help distinguish session keys in Redis
app.config['SESSION_REDIS'] = Redis(host='127.0.0.1', port=6379)  # Connect to your Redis instance on the server

# Set up sessions with Redis
Session(app)

# Configure logging
logging.basicConfig(level=logging.INFO)  # Adjust to INFO for production
logger = logging.getLogger(__name__)

# Set up database
DATABASE_PATH = config.DATABASE_PATH
setup_database(DATABASE_PATH)

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

#####################################################################
# routes to select user's email which is required to retrieve user sub which is required for API calls to CORE

@app.route('/select_user_email_get', methods=['GET'])
def select_user_email_get():
    next_url = url_for('fetch_project_number_get')  # URL to go to after selecting the email
    emails = get_all_emails()  # Retrieve emails from the database
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

    return redirect(next_url or url_for('home'))

#####################################################################
# GET and POST routes to enter a project number and to search a project by number
# GET route to display project number entry form
@app.route('/fetch_project_number', methods=['GET'])
def fetch_project_number_get():
    return render_template('select_project_number.html')  # Updated template name

# POST route to handle project number submission
@app.route('/fetch_project_number_submit', methods=['POST'])
def fetch_project_number_post():
    selected_email = session.get('selected_email')
    if not selected_email:
        flash('No email selected. Please select an email first.', 'error')
        return redirect(url_for('select_user_email_get'))
    
    project_number = request.form.get('project_number')
    if not project_number:
        flash('Please enter a project number.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Fetch project details from the backend using selected email and project number
    project_data = get_project_by_code(project_number, selected_email)
    
    if not project_data:
        flash('Project not found. Please check the Project ID and try again.', 'error')
        return redirect(url_for('fetch_project_number_get'))
    
    # Create project and client objects from the retrieved data
    project = Project.from_dict(project_data[0])
    client_data = get_client_by_id(project.client_id, selected_email)
    client = Client.from_dict(client_data[0]) if client_data else None
    
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
    
    # Redirect to the display page route
    return redirect(url_for('display_project_client_details'))

############################################################
# app route to display the project and client details for the user
# Route to display project and client details
@app.route('/display_project_client_details', methods=['GET'])
def display_project_client_details():
    project = session.get('project_data', {})
    client = session.get('client_data', {})
    return render_template('display_project_client_details.html', project=project, client=client)

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

@app.route('/store_amendment_results', methods=['POST'])
def store_amendment_results():
    # Retrieve AHJ data and amendment data from the session
    ahj_data = session.get('ahj_data')
    pdf_links = session.get('amendment_pdf_links')
    web_links = session.get('amendment_web_links')

    # Ensure AHJ data is available before storing
    if not ahj_data:
        flash("No AHJ data found. Please perform an AHJ search first.", 'error')
        return redirect(url_for('fetch_ahj_address_get'))
    
    # Store both AHJ data and amendment data in session
    session['stored_ahj_data'] = ahj_data
    session['stored_amendment_pdf_links'] = pdf_links
    session['stored_amendment_web_links'] = web_links
    
    flash("Both AHJ and amendment data stored for export.", 'success')
    return redirect(url_for('home'))

###############################################################
# app routes to handle exporting the project, client, AHJ, and amendment info fetched by the user to a csv/excel workbook

@app.route('/display_report_details', methods=['GET'])
def display_report_details_get():
    # Retrieve all necessary data from the session
    project = session.get('confirmed_project_data', {})
    client = session.get('confirmed_client_data', {})
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

##################################
# app routes to launch application and exit application

# clears all session data for the user and returns them to the home page
# should close app but not working
@app.route('/exit_app')
def exit_app():
    session.clear()  # Clear all session data for the user
    flash("You have been logged out. Session data cleared.")
    return redirect(url_for('home'))

"""
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
    # Start the browser-opening function in a separate thread
    threading.Thread(target=open_browser).start()
    # Launch the Flask app
    app.run(port=8000, use_reloader=False)
    """
