#/api/routes/soil_routes.py
# ================================
"""
USDA Soil Survey routes
Handles soil survey report generation with background processing
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash
from threading import Thread
import logging
import uuid

# Import from your new structure
from app.services.project.project_manager import get_project_by_code
from app.services.project.export_project_details import find_project_directory
from app.services.soil.soil_scraper import WebSoilSurveyScraper, SoilScraperConfig
from app.core.models import Project
from app.api.utils.background_tasks import _execute_individual_soil_survey_with_progress
from app.api.utils.progress_tracking import SingleStepProgressTracker
from app.api.utils.validation import _validate_individual_soil_request

# Create blueprint
soil_bp = Blueprint('soil', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# SOIL SURVEY ROUTES
# =============================================================================
"""
App route to handle scraping and downloading both USDA Soil Reports:
    - Linear Extensability
    - Unified Soil Classification
"""
@soil_bp.route('/generate_soil_survey', methods=['GET', 'POST'])
def generate_soil_survey():
    """
    Updated Soil Survey route with progress tracking
    """
    if request.method == 'GET':
        # Existing GET logic (your current implementation)
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('auth.select_user_email_get'))

        project_number = request.args.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
            
        # Get and validate project data (your existing logic)
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        project = Project.from_dict(project_data[0])
        if not all([project.street1, project.city, project.state, project.zip_code]):
            flash('Project address is incomplete. Please verify the project has a complete address.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
        return redirect(url_for('auth.home'))

"""
End of USDA Soil Reports App Route
"""