#app/api/routes/ahj_routes.py
# ===============================
"""
AHJ (Authority Having Jurisdiction) routes
Handles AHJ report generation, display, export, and cover letter generation
Updated to use Google Search Service instead of Bing
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash
import logging
import uuid
from threading import Thread
import os

# Import from your new structure
from app.core.database import get_user_details_by_email
from app.services.project.project_manager import get_project_by_code, get_client_by_id
from app.services.project.export_project_details import create_workbook, insert_project_data, insert_client_data, insert_ahj_data, save_workbook
from app.services.ahj.ahj_manager import search_ahj_registry
from app.services.google_search.google_search_service import GoogleSearchService, SearchResult
from app.core.models import Project, Client
from app.core.config import Config

# Create blueprint
ahj_bp = Blueprint('ahj', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# AHJ REPORT GENERATION ROUTES
# =============================================================================
"""
App routes to query to the AHJ registry for IBC codes, query BQE endpoints for project and client data, and
perform Google searches for web links and building code amendments
Displays the information for user to confirm before exporting
"""
@ahj_bp.route('/generate_ahj_report', methods=['POST'])
def generate_ahj_report():
    """
    Consolidated route to generate complete AHJ report including project details,
    AHJ information, and amendments. Now uses Google Search Service for finding
    building code amendments.
    """
    try:
        # Get required session data
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('auth.select_user_email_get'))
        
        project_number = request.form.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

        # Step 1: Fetch project and client details
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        # Create Project instance using the model's from_dict method
        project = Project.from_dict(project_data[0])
        
        # Validate project address - critical for AHJ search
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address before generating an AHJ report.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
            session['stored_amendment_links'] = []
            return redirect(url_for('ahj.display_report_details_get'))

        # Step 3: Search for amendments using Google Search Service
        amendment_links = []
        try:
            if ahj_data and len(ahj_data) > 0:
                ahj_name = ahj_data[0].get('AHJ Name')
                if ahj_name:
                    state = project.state
                    
                    # Initialize Google Search Service
                    google_api_key = os.environ.get('GOOGLE_API_KEY', Config.GOOGLE_API_KEY)
                    google_search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID', Config.GOOGLE_SEARCH_ENGINE_ID)
                    
                    if not google_api_key or not google_search_engine_id:
                        logger.error("Google Search API credentials not configured")
                        flash('Amendment search is not configured. Please contact administrator.', 'warning')
                    else:
                        # Use Google Search Service to find building code amendments
                        search_service = GoogleSearchService(google_api_key, google_search_engine_id)
                        
                        # Search for amendments - returns up to 10 ranked results
                        search_results = search_service.search_ahj_amendments(ahj_name, state)
                        
                        # Convert SearchResult objects to the format expected by the template
                        for result in search_results:
                            amendment_links.append({
                                'name': result.title,
                                'url': result.link,
                                'snippet': result.snippet,
                                'file_format': result.file_format,
                                'priority_tier': result.priority_tier
                            })
                        
                        search_service.close()
                        
                        logger.info(f"Found {len(amendment_links)} amendment links for {ahj_name}, {state}")
                        
        except Exception as e:
            logger.error(f"Error searching amendments: {str(e)}")
            flash('Amendment search failed. The report will be generated with AHJ information but without amendments.', 'warning')

        # Store AHJ and amendment data in session
        session['stored_ahj_data'] = ahj_data
        session['stored_amendment_links'] = amendment_links

        # Success - redirect to display
        flash('Report data generated successfully.', 'success')
        return redirect(url_for('ahj.display_report_details_get'))

    except Exception as e:
        logger.error(f"Error generating AHJ report: {str(e)}")
        flash('An error occurred while generating the report. Please try again or generate the report in steps using the individual functions.', 'error')
        return redirect(url_for('auth.home'))

"""End of unified process"""

"""App routes to display AHJ report details and to export the reports to the appropriate project directory"""
@ahj_bp.route('/display_report_details', methods=['GET'])
def display_report_details_get():
    """
    Display the generated AHJ report details for user confirmation.
    Updated to handle unified amendment links instead of separate PDF/web links.
    """
    # Retrieve all necessary data from the session
    project = session.get('confirmed_project_data', {})
    logger.debug(f"Project data passed to display_report_details: {project}")
    
    client = session.get('confirmed_client_data', {})
    logger.debug(f"Client data passed to display_report_details: {client}")
    
    ahj_data = session.get('stored_ahj_data', [])
    amendment_links = session.get('stored_amendment_links', [])
    
    # For backward compatibility, if old session variables exist, combine them
    if 'stored_amendment_pdf_links' in session or 'stored_amendment_web_links' in session:
        logger.info("Migrating old session data format to new unified format")
        old_pdf_links = session.pop('stored_amendment_pdf_links', [])
        old_web_links = session.pop('stored_amendment_web_links', [])
        
        # Combine old format into new format if amendment_links is empty
        if not amendment_links:
            amendment_links = []
            for link in old_pdf_links:
                link['file_format'] = 'PDF'
                link['priority_tier'] = 5
                amendment_links.append(link)
            
            for link in old_web_links:
                link['file_format'] = None
                link['priority_tier'] = 5
                amendment_links.append(link)
            
            session['stored_amendment_links'] = amendment_links

    return render_template(
        'display_report_details.html',
        project=project,
        client=client,
        ahj_data=ahj_data,
        amendment_links=amendment_links  # Single list of all links
    )

# exports the data and saves it in an excel workbook in the jobs directory
@ahj_bp.route('/export_report', methods=['POST'])
def export_report_post():
    """
    Export the AHJ report data to an Excel workbook.
    Updated to handle unified amendment links.
    """
    # Retrieve data from the session
    project_data = session.get('confirmed_project_data')
    client_data = session.get('confirmed_client_data')
    ahj_data = session.get('stored_ahj_data')
    amendment_links = session.get('stored_amendment_links', [])

    # Verify project_data and client_data are available
    if not project_data or not client_data:
        flash("Missing project or client data. Please confirm details again.", 'error')
        return redirect(url_for('ahj.display_report_details_get'))

    # Create workbook and insert data
    workbook = create_workbook()
    sheet = workbook.active
    
    # Debug log for project_data
    logger.debug(f"Project data contents: {project_data}")
    
    insert_project_data(sheet, project_data)
    insert_client_data(sheet, client_data)
    
    # Convert amendment_links to the format expected by insert_ahj_data
    # The function expects a dict with 'pdf_links' and 'web_links'
    amendments = {
        "pdf_links": [],
        "web_links": []
    }
    
    for link in amendment_links:
        if link.get('file_format') == 'PDF' or link.get('url', '').lower().endswith('.pdf'):
            amendments["pdf_links"].append({
                'name': link.get('name', ''),
                'url': link.get('url', '')
            })
        else:
            amendments["web_links"].append({
                'name': link.get('name', ''),
                'url': link.get('url', '')
            })
    
    insert_ahj_data(sheet, ahj_data, amendments)

    # Save the workbook and provide feedback
    saved_path = save_workbook(workbook, project_data['code'])
    if saved_path:
        flash(f"Workbook successfully saved at {saved_path}", 'success')
        return redirect(url_for('auth.home'))
    else:
        flash("Failed to save workbook. Please try again.", 'error')
        return redirect(url_for('ahj.display_report_details_get'))