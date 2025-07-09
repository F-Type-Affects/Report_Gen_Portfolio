# app/api/utils/progress_tracking.py
# ====================================
"""
Centralized progress tracking utilities
Provides thread-safe progress tracking classes and global progress storage
"""

import logging

# Get logger
logger = logging.getLogger(__name__)

# Global dictionary to store progress for each session
# This is shared across all routes and background tasks
progress_tracker = {}

class ProgressTracker:
    """Thread-safe progress tracker for long-running operations"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.reset()
    
    def reset(self):
        """Reset progress to initial state"""
        progress_tracker[self.session_id] = {
            'overall_progress': 0,
            'current_step': 0,
            'steps': [
                {'name': 'ASCE Full Report', 'status': 'pending', 'progress': 0},
                {'name': 'Soil Survey', 'status': 'pending', 'progress': 0},
                {'name': 'ASCE Summary', 'status': 'pending', 'progress': 0}
            ],
            'status': 'starting',
            'message': 'Initializing...',
            'error': None,
            'completed': False
        }
    
    def update_step(self, step_index, status, progress=None, message=None):
        """Update a specific step's progress"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        if 0 <= step_index < len(data['steps']):
            data['steps'][step_index]['status'] = status
            if progress is not None:
                data['steps'][step_index]['progress'] = progress
            
            # Update current step
            data['current_step'] = step_index
            
            # Calculate overall progress
            total_progress = sum(step['progress'] for step in data['steps'])
            data['overall_progress'] = total_progress / 3  # 3 steps total
            
            # Update global status and message
            if message:
                data['message'] = message
            
            if status == 'completed':
                # Check if all steps are completed
                if all(step['status'] == 'completed' for step in data['steps']):
                    data['status'] = 'completed'
                    data['completed'] = True
                    data['message'] = 'All reports generated successfully!'
            elif status == 'error':
                data['status'] = 'error'
                data['error'] = message
    
    def set_error(self, error_message):
        """Set error state"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['status'] = 'error'
        data['error'] = error_message
        data['message'] = f'Error: {error_message}'

class SingleStepProgressTracker:
    """Simplified progress tracker for single-step operations"""
    
    def __init__(self, session_id, step_name):
        self.session_id = session_id
        self.step_name = step_name
        self.reset()
    
    def reset(self):
        """Reset progress to initial state"""
        progress_tracker[self.session_id] = {
            'overall_progress': 0,
            'current_step': 0,
            'steps': [
                {'name': self.step_name, 'status': 'pending', 'progress': 0}
            ],
            'status': 'starting',
            'message': 'Initializing...',
            'error': None,
            'completed': False
        }
    
    def update_progress(self, progress, message=None, status='in_progress'):
        """Update progress for the single step"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['steps'][0]['status'] = status
        data['steps'][0]['progress'] = progress
        data['overall_progress'] = progress
        
        if message:
            data['message'] = message
        
        if status == 'completed':
            data['status'] = 'completed'
            data['completed'] = True
            data['message'] = f'{self.step_name} generated successfully!'
        elif status == 'error':
            data['status'] = 'error'
            data['error'] = message
    
    def set_error(self, error_message):
        """Set error state"""
        if self.session_id not in progress_tracker:
            return
            
        data = progress_tracker[self.session_id]
        data['status'] = 'error'
        data['error'] = error_message
        data['message'] = f'Error: {error_message}'
        data['steps'][0]['status'] = 'error'