# app/api/utils/validation.py
# =============================
"""
Centralized request validation utilities
Provides common validation functions used across multiple route handlers
"""

from flask import session, request, url_for
import logging



# Get logger
logger = logging.getLogger(__name__)



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
                'redirect': url_for('auth.select_user_email_get')
            }
        
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('project.fetch_project_number_get')
            }
        
        # Get ASCE form options from request
        standard_version = request.form.get('standard_version')
        risk_category = request.form.get('risk_category')
        soil_class = request.form.get('soil_class')

        if not all([standard_version, risk_category, soil_class]):
            return {
                'error': True,
                'message': 'Please select all required ASCE options.',
                'redirect': url_for('asce.generate_asce_full_report')
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
            'redirect': url_for('auth.home')
        }

#######################################################################

def _validate_individual_soil_request():
    """Validate soil survey individual request"""
    try:
        selected_email = session.get('selected_email')
        if not selected_email:
            return {
                'error': True,
                'message': 'No email selected. Please select an email first.',
                'redirect': url_for('auth.select_user_email_get')
            }
        
        project_data = session.get('project_data')
        if not project_data or not project_data.get('code'):
            return {
                'error': True,
                'message': 'Project data not found. Please try again.',
                'redirect': url_for('project.fetch_project_number_get')
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
            'redirect': url_for('auth.home')
        }

############################################################################
