# app/api/routes/workflow_routes.py
# ===================================
"""
Unified workflow routes
Handles the complex "generate all reports" functionality that orchestrates multiple services
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash
from threading import Thread
import logging
import uuid

# Import from your new structure
from app.services.project.project_manager import get_project_by_code
from app.services.project.export_project_details import find_report_workbook, find_project_directory, update_workbook_with_summary
from app.services.asce.asce_hazard_report import ASCEReportScraper
from app.services.asce.asce_hazard_summary import ASCEScraper
from app.services.soil.soil_scraper import WebSoilSurveyScraper, SoilScraperConfig
from app.core.models import Project, Client
from app.api.utils.background_tasks import _execute_unified_scraping_with_progress
from app.api.utils.progress_tracking import ProgressTracker

# Create blueprint
workflow_bp = Blueprint('workflow', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# UNIFIED WORKFLOW ROUTES
# =============================================================================
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
@workflow_bp.route('/generate_all_reports', methods=['GET', 'POST'])
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
        return redirect(url_for('auth.home'))

#####################################################################

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
            return redirect(url_for('auth.select_user_email_get'))

        # Get and validate project number
        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
            
        # Fetch and validate project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        # Create Project instance and validate address
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. All web scraping reports require a complete address.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
        return redirect(url_for('auth.home'))
    
##############################################################

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
                'redirect': url_for('auth.select_user_email_get')
            }
        
        # Validate project data in session
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('project.fetch_project_number_get')
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
                'redirect': url_for('project.fetch_project_number_get')
            }
        
        # Validate ASCE form options
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            return {
                'error': True,
                'message': 'Please select all required ASCE options.',
                'redirect': url_for('workflow.generate_all_reports')
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
            'redirect': url_for('auth.home')
        }

###############################################################