"""
Enhanced Cover Letter generation routes
Supports multiple templates with flexible template selection
"""

from flask import Blueprint, request, session, render_template, redirect, url_for, flash, jsonify
import logging
import uuid
from threading import Thread
from typing import Dict, Any, Optional
from datetime import datetime

from app.services.project.cover_letter import sml_cover_letter_generator
from app.services.project.coverletter_template_manager import template_manager
from app.core.database import get_user_details_by_email
from app.services.project.project_manager import get_project_by_code, get_client_by_id
from app.core.models import Project, Client

# Create blueprint
cover_letter_bp = Blueprint('cover_letter', __name__)

# Get logger
logger = logging.getLogger(__name__)

# =============================================================================
# COVER LETTER TEMPLATE SELECTION ROUTES
# =============================================================================

@cover_letter_bp.route('/select_template', methods=['GET'])
def select_cover_letter_template():
    """
    Display template selection page
    """
    try:
        # Validate user session
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('auth.select_user_email_get'))
        
        # Get project data from session
        project_data = session.get('project_data')
        if not project_data:
            flash('No project selected. Please select a project first.', 'error')
            return redirect(url_for('project.fetch_project_number_get'))
        
        # Get available templates and options
        available_templates = template_manager.get_available_templates()
        engineer_initials_options = template_manager.get_engineer_initials_options()
        pool_standard_options = template_manager.get_pool_standard_options()
        
        if not available_templates:
            flash('No cover letter templates are currently available.', 'error')
            return redirect(url_for('auth.home'))
        
        # Get user details for display
        user_details = get_user_details_by_email(selected_email)
        if not user_details:
            flash('User details not found.', 'error')
            return redirect(url_for('auth.home'))
        
        return render_template('select_coverletter_template.html',
                             templates=available_templates,
                             engineer_initials_options=engineer_initials_options,
                             pool_standard_options=pool_standard_options,
                             project_data=session['project_data'],
                             first_name=user_details.get('first_name'),
                             last_name=user_details.get('last_name'))
                             
    except Exception as e:
        logger.error(f"Error displaying template selection: {str(e)}")
        flash('An error occurred while loading template options. Please try again.', 'error')
        return redirect(url_for('auth.home'))

@cover_letter_bp.route('/template_info/<template_id>', methods=['GET'])
def get_template_info(template_id: str):
    """
    API endpoint to get template information and requirements
    """
    try:
        template_config = template_manager.get_template_config(template_id)
        if not template_config:
            return jsonify({'error': 'Template not found'}), 404
        
        requirements = template_manager.get_template_requirements(template_id)
        
        return jsonify({
            'template_id': template_config.template_id,
            'display_name': template_config.display_name,
            'description': template_config.description,
            'template_type': template_config.template_type.value,
            'required_fields': requirements['required_fields'],
            'optional_fields': requirements['optional_fields']
        })
        
    except Exception as e:
        logger.error(f"Error getting template info for {template_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# =============================================================================
# ENHANCED COVER LETTER GENERATION ROUTES  
# =============================================================================
@cover_letter_bp.route('/generate_cover_letter', methods=['POST'])
def generate_cover_letter():
    """
    Enhanced route to handle cover letter generation requests with template selection
    """
    try:
        # Validate user session
        selected_email = session.get('selected_email')
        if not selected_email:
            flash('No email selected. Please select an email first.', 'error')
            return redirect(url_for('auth.select_user_email_get'))

        # Get project number and template selection from form
        project_number = request.form.get('project_number')
        template_id = request.form.get('template_id')
        engineer_initials = request.form.get('engineer_initials')
        pool_standard = request.form.get('pool_standard')
        
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

        logger.debug(f"Client data type after session['client_data']: {type(client_data)}")
        logger.debug(f"Client data content after session['client_data']: {client_data}")
        
        # Get user details for display
        user_details = get_user_details_by_email(selected_email)
        if not user_details:
            flash('User details not found.', 'error')
            return redirect(url_for('auth.home'))

        # If template_id was provided, proceed to confirmation
        if template_id:
            
            logger.debug(f"About to render template with template_id: {template_id}")
            logger.debug(f"Template manager type: {type(template_manager)}")
            
            try:
                template_config = template_manager.get_template_config(template_id)
                logger.debug(f"Template config retrieved successfully: {template_config is not None}")
            except Exception as template_error:
                logger.error(f"Error in get_template_config: {template_error}")
                raise template_error
            
            if template_config:
                # Store template selection in session
                session['selected_template_id'] = template_id
                session['selected_engineer_initials'] = engineer_initials
                session['selected_pool_standard'] = pool_standard
                
                # Prepare template info for display
                template_info = {
                    'template_id': template_config.template_id,
                    'display_name': template_config.display_name,
                    'description': template_config.description,
                    'has_engineer_initials': template_config.has_engineer_initials,
                    'has_checked_by': template_config.has_checked_by,
                    'has_pool_standard': template_config.has_pool_standard,
                    'client_format': template_config.client_format
                }
                
                
                return render_template('display_letter_details.html',
                     project_data=session['project_data'],
                     client_data=session['client_data'],
                     template_info=template_info,
                     engineer_initials=engineer_initials,
                     pool_standard=pool_standard,
                     first_name=user_details.get('first_name'),
                     last_name=user_details.get('last_name'),
                     current_date=datetime.now().strftime('%m/%d/%y'))
                
        
        # Otherwise, redirect to template selection
        return redirect(url_for('cover_letter.select_cover_letter_template'))

    except Exception as e:
        logger.error(f"Error preparing cover letter data: {str(e)}")
        flash('An error occurred while preparing the cover letter. Please try again.', 'error')
        return redirect(url_for('auth.home'))

@cover_letter_bp.route('/generate_with_template', methods=['POST'])
def generate_cover_letter_with_template():
    """
    Generate cover letter with selected template
    """
    try:
        selected_email = session.get('selected_email')
        template_id = request.form.get('template_id') or session.get('selected_template_id')
        
        if not template_id:
            flash('No template selected. Please select a template.', 'error')
            return redirect(url_for('cover_letter.select_cover_letter_template'))
        
        # Validate template exists
        if not template_manager.validate_template_exists(template_id):
            flash('Selected template is not available. Please choose another template.', 'error')
            return redirect(url_for('cover_letter.select_cover_letter_template'))
        
        # Get user details
        user_details = get_user_details_by_email(selected_email)
        if not user_details:
            flash('User details not found.', 'error')
            return redirect(url_for('auth.home'))
        
        # Prepare user data
        user_data = {
            'first_name': user_details.get('first_name', ''),
            'last_name': user_details.get('last_name', ''),
            'email': selected_email
        }
        
        # Get template-specific options from form
        engineer_initials = request.form.get('engineer_initials')
        pool_standard = request.form.get('pool_standard')
        
        # Validate template requirements
        template_config = template_manager.get_template_config(template_id)
        if template_config:
            # Validate pool standard for templates requiring it
            if template_config.has_pool_standard:
                if not pool_standard or not template_manager.validate_pool_standard(pool_standard):
                    flash('Please select a valid pool standard for this template.', 'error')
                    return redirect(url_for('cover_letter.select_cover_letter_template'))
            
            # Validate engineer initials for pool templates
            if template_config.has_engineer_initials:
                if not engineer_initials or not template_manager.validate_engineer_initials(engineer_initials):
                    flash('Please select valid engineer initials for pool templates.', 'error')
                    return redirect(url_for('cover_letter.select_cover_letter_template'))
        
        # Generate cover letter
        success, message = sml_cover_letter_generator.generate_cover_letter(
            template_id=template_id,
            project_data=session['project_data'],
            client_data=session['client_data'],
            user_data=user_data,
            engineer_initials=engineer_initials,
            pool_standard=pool_standard
        )

        if success:
            flash(message, 'success')
        else:
            flash(f'Failed to generate cover letter: {message}', 'error')

        return redirect(url_for('auth.home'))

    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        flash('An error occurred while generating the cover letter. Please try again.', 'error')
        return redirect(url_for('auth.home'))

# =============================================================================
# UTILITY ROUTES
# =============================================================================

@cover_letter_bp.route('/available_templates', methods=['GET'])
def get_available_templates():
    """
    API endpoint to get all available templates
    """
    try:
        templates = template_manager.get_available_templates()
        return jsonify({'templates': templates})
    except Exception as e:
        logger.error(f"Error getting available templates: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

"""End of Enhanced Cover Letter routes"""