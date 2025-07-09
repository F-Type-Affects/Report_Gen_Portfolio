# app/api/routes/progress_routes.py
# ===================================
"""
Progress tracking routes
Handles real-time progress updates via Server-Sent Events (SSE)
"""

from flask import Blueprint, Response
import json
import time
import logging
import uuid
from threading import Thread

# Create blueprint
progress_bp = Blueprint('progress', __name__)

# Get logger
logger = logging.getLogger(__name__)

# TODO: Import this from app/api/utils/progress_tracking.py when created
# For now, accessing the global progress tracker
# This should be centralized once we extract shared utilities
progress_tracker = {}

@progress_bp.route('/progress/<session_id>')
def progress_stream(session_id):
    """
    Server-Sent Events endpoint for real-time progress updates
    """
    def generate_progress():
        """Generator function for SSE stream"""
        while True:
            if session_id in progress_tracker:
                data = progress_tracker[session_id]
                yield f"data: {json.dumps(data)}\n\n"
                
                # Stop streaming if completed or error
                if data.get('completed') or data.get('status') == 'error':
                    break
            else:
                # No progress data available
                yield f"data: {json.dumps({'status': 'no_data'})}\n\n"
            
            time.sleep(1)  # Update every second
    
    return Response(
        generate_progress(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )