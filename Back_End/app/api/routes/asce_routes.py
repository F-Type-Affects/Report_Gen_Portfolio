# app/api/routes/asce_routes.py
# ===============================
"""
ASCE (American Society of Civil Engineers) hazard analysis routes
Handles ASCE hazard summary and full report generation with background processing
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash
from threading import Thread
import logging
import uuid

# Import from your new structure
from app.core.database import get_user_details_by_email
from app.services.project.project_manager import get_project_by_code
from app.services.project.export_project_details import  update_workbook_with_summary, find_report_workbook, find_project_directory
from app.services.asce.asce_hazard_summary import ASCEScraper
from app.services.asce.asce_hazard_report import ASCEReportScraper
from app.core.models import Project, ASCESummaryData, WindData, SeismicData, IceData, SnowData
from app.api.utils.progress_tracking import SingleStepProgressTracker, progress_tracker
from app.api.utils.validation import _validate_individual_asce_request
from app.api.utils.background_tasks import _execute_individual_asce_summary_with_progress, _execute_individual_asce_report_with_progress

# Create blueprint
asce_bp = Blueprint('asce', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# ASCE SUMMARY ROUTES
# =============================================================================
"""
App routes to scrape ASCE hazard tool for summary table and Full Report
"""
"""
This app route handles scraping the ASCE site for the summary table
"""
@asce_bp.route('/generate_asce_summary', methods=['GET', 'POST'])
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
            return redirect(url_for('auth.select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
            
        # Get project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        # Create Project instance
        project = Project.from_dict(project_data[0])
        
        # Validate project address
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
        return redirect(url_for('auth.home'))

@asce_bp.route('/display_asce_summary_results')
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
            return redirect(url_for('auth.home'))
        
        # Retrieve data from progress tracker
        tracker_data = progress_tracker[progress_session_id]
        summary_dict = tracker_data.get('summary_data')
        project_data = tracker_data.get('project_data')
        
        if not project_data or not summary_dict:
            flash('Summary data incomplete. Please try generating the summary again.', 'error')
            return redirect(url_for('auth.home'))
        
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
        return redirect(url_for('auth.home'))

"""
This app route saves the extracted summary table to the AHJ report workbook after the results are displayed to the user
"""
@asce_bp.route('/save_summary_report', methods=['POST'])
def save_summary_report():
    try:
        project_number = session.get('project_data', {}).get('code')
        summary_dict = session.get('summary_data')
        
        if not project_number or not summary_dict:
            flash('Missing required data. Please try again.', 'error')
            return redirect(url_for('auth.home'))
            
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
            
        return redirect(url_for('auth.home'))
        
    except Exception as e:
        logger.error(f"Error saving summary report: {str(e)}")
        flash('An unexpected error occurred while saving the report.', 'error')
        return redirect(url_for('auth.home'))
# =============================================================================
# ASCE FULL REPORT ROUTES
# =============================================================================
"""
This app route handles scraping the ASCE website for the the full report and saves it to the appropriate project sub directory
"""
@asce_bp.route('/generate_asce_full_report', methods=['GET', 'POST'])
def generate_asce_full_report():
    """
    Updated ASCE Full Report route with progress tracking
    """
    if request.method == 'GET':
        # Existing GET logic (display form)
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('auth.select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
            
        # Get and validate project data
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
        return redirect(url_for('auth.home'))
"""
End of ASCE web scraping app routes
"""