#app/api/routes/cover_letter_routes.py
# ===============================
"""
Cover Letter generation routes
Handles generating cover letters for various engineering reports
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash
import logging
import uuid
from threading import Thread

from app.services.project.cover_letter import generate_cover_letter
from app.core.database import get_user_details_by_email
from app.services.project.project_manager import get_project_by_code, get_client_by_id
from app.core.models import Project, Client

# Create blueprint
cover_letter_bp = Blueprint('cover_letter', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# AHJ REPORT GENERATION ROUTES
# =============================================================================
"""App route to generate cover letter.
   Allows for all process be to be done in any order
"""
@cover_letter_bp.route('/generate_cover_letter', methods=['POST'])
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
            return redirect(url_for('auth.select_user_email_get'))

        # Get and validate project number from form
        project_number = request.form.get('project_number')
        if not project_number:
            flash('Please enter a project number.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

        # Always fetch fresh project data for the requested project number
        logger.info(f"Fetching data for project number: {project_number}")
        project_data = get_project_by_code(project_number, selected_email)
        if not project_data:
            flash('Project not found. Please check the Project ID and try again.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

        # Create Project instance and fetch related client data
        project = Project.from_dict(project_data[0])
        client_data = get_client_by_id(project.client_id, selected_email)
        if not client_data:
            flash('Client data not found.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))

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
            return redirect(url_for('auth.home'))

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
        return redirect(url_for('auth.home'))

@cover_letter_bp.route('/generate_cover_letter_confirmed', methods=['POST'])
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

        return redirect(url_for('auth.home'))

    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        flash('An error occurred while generating the cover letter. Please try again.', 'error')
        return redirect(url_for('auth.home'))

"""End of Cover Letter specefic app route
"""
