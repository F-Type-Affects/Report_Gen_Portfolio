# app/api/routes/project_routes.py
# =================================
"""
Project management routes
Handles project number selection and basic project operations
"""

from flask import Blueprint, request, render_template
import uuid
from threading import Thread

import logging

# Create blueprint
project_bp = Blueprint('project', __name__)

# =============================================================================
# PROJECT SELECTION ROUTES
# =============================================================================
"""
App route allows the other app routes to redirect back to the search project number template
"""
@project_bp.route('/fetch_project_number', methods=['GET'])
def fetch_project_number_get():
    next_url = request.args.get('next') 
    return render_template('select_project_number.html', next_url=next_url)

"""
"""