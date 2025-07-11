# app/api/utils/progress_tracking.py
# ====================================
"""
Centralized progress tracking utilities - FIXED VERSION
Provides thread-safe progress tracking classes and global progress storage
"""

import logging
import threading
import time
from app.api.routes.progress_routes import progress_tracker

# Get logger
logger = logging.getLogger(__name__)

# Thread lock for progress tracker operations
_progress_lock = threading.Lock()

class ProgressTracker:
    """Thread-safe progress tracker for long-running operations"""
    
    def __init__(self, session_id):
        self.session_id = session_id
        self.reset()
    
    def reset(self):
        """Reset progress to initial state - THREAD SAFE"""
        with _progress_lock:
            # Explicitly clean up any existing session data first
            if self.session_id in progress_tracker:
                logger.debug(f"Cleaning up existing progress data for session: {self.session_id}")
                del progress_tracker[self.session_id]
            
            # Initialize with clean state
            progress_tracker[self.session_id] = {
                'overall_progress': 0,  # Explicitly set to 0
                'current_step': 0,
                'steps': [
                    {'name': 'ASCE Full Report', 'status': 'pending', 'progress': 0},
                    {'name': 'Soil Survey', 'status': 'pending', 'progress': 0},
                    {'name': 'ASCE Summary', 'status': 'pending', 'progress': 0}
                ],
                'status': 'starting',
                'message': 'Initializing...',
                'error': None,
                'completed': False,
                'created_at': time.time()  # Add timestamp for cleanup
            }
            logger.debug(f"Initialized progress tracker for session {self.session_id} with clean state")
    
    def update_step(self, step_index, status, progress=None, message=None):
        """Update a specific step's progress - THREAD SAFE"""
        with _progress_lock:
            if self.session_id not in progress_tracker:
                logger.warning(f"Session {self.session_id} not found in progress tracker")
                return
                
            data = progress_tracker[self.session_id]
            if 0 <= step_index < len(data['steps']):
                # Update step data
                data['steps'][step_index]['status'] = status
                if progress is not None:
                    # Ensure progress is within valid range
                    progress = max(0, min(100, progress))
                    data['steps'][step_index]['progress'] = progress
                
                # Update current step
                data['current_step'] = step_index
                
                # Calculate overall progress - FIXED CALCULATION
                total_progress = sum(step['progress'] for step in data['steps'])
                data['overall_progress'] = total_progress / 3  # 3 steps total
                
                # Update global status and message
                if message:
                    data['message'] = message
                
                # Update global status based on step status
                if status == 'in_progress':
                    data['status'] = 'in_progress'
                elif status == 'completed':
                    # Check if all steps are completed
                    if all(step['status'] == 'completed' for step in data['steps']):
                        data['status'] = 'completed'
                        data['completed'] = True
                        data['message'] = 'All reports generated successfully!'
                elif status == 'error':
                    data['status'] = 'error'
                    data['error'] = message
                
                logger.debug(f"Updated step {step_index} for session {self.session_id}: "
                           f"status={status}, progress={progress}, overall={data['overall_progress']}")
    
    def set_error(self, error_message):
        """Set error state - THREAD SAFE"""
        with _progress_lock:
            if self.session_id not in progress_tracker:
                logger.warning(f"Session {self.session_id} not found in progress tracker")
                return
                
            data = progress_tracker[self.session_id]
            data['status'] = 'error'
            data['error'] = error_message
            data['message'] = f'Error: {error_message}'
            logger.error(f"Set error for session {self.session_id}: {error_message}")

class SingleStepProgressTracker:
    """Simplified progress tracker for single-step operations - FIXED VERSION"""
    
    def __init__(self, session_id, step_name):
        self.session_id = session_id
        self.step_name = step_name
        self.reset()
    
    def reset(self):
        """Reset progress to initial state - THREAD SAFE and CLEAN"""
        with _progress_lock:
            # CRITICAL FIX: Explicitly clean up any existing session data first
            if self.session_id in progress_tracker:
                logger.debug(f"Cleaning up existing progress data for session: {self.session_id}")
                del progress_tracker[self.session_id]
            
            # Initialize with completely fresh state
            progress_tracker[self.session_id] = {
                'overall_progress': 0,  # EXPLICITLY set to 0
                'current_step': 0,
                'steps': [
                    {'name': self.step_name, 'status': 'pending', 'progress': 0}  # EXPLICITLY set to 0
                ],
                'status': 'starting',
                'message': 'Initializing...',
                'error': None,
                'completed': False,
                'created_at': time.time()  # Add timestamp for cleanup
            }
            logger.debug(f"Initialized single-step progress tracker for session {self.session_id} "
                        f"with step '{self.step_name}' - clean state confirmed")
    
    def update_progress(self, progress, message=None, status='in_progress'):
        """Update progress for the single step - THREAD SAFE with PROPER LOGIC"""
        with _progress_lock:
            if self.session_id not in progress_tracker:
                logger.warning(f"Session {self.session_id} not found in progress tracker")
                return
                
            data = progress_tracker[self.session_id]
            
            # Ensure progress is within valid range
            progress = max(0, min(100, progress))
            
            # Update step progress
            data['steps'][0]['status'] = status
            data['steps'][0]['progress'] = progress
            
            # CRITICAL FIX: For single step, overall_progress = step progress
            data['overall_progress'] = progress
            
            # Update global status based on progress and status
            if progress > 0 and status == 'in_progress':
                data['status'] = 'in_progress'  # Change from 'starting' to 'in_progress'
            elif status == 'completed':
                data['status'] = 'completed'
                data['completed'] = True
                data['overall_progress'] = 100  # Ensure it's exactly 100 when completed
                data['message'] = f'{self.step_name} generated successfully!'
            elif status == 'error':
                data['status'] = 'error'
                data['error'] = message
            
            # Update message if provided
            if message and status != 'completed':  # Don't override completion message
                data['message'] = message
            
            logger.debug(f"Updated progress for session {self.session_id}: "
                        f"progress={progress}, status={status}, overall={data['overall_progress']}")
    
    def set_error(self, error_message):
        """Set error state - THREAD SAFE"""
        with _progress_lock:
            if self.session_id not in progress_tracker:
                logger.warning(f"Session {self.session_id} not found in progress tracker")
                return
                
            data = progress_tracker[self.session_id]
            data['status'] = 'error'
            data['error'] = error_message
            data['message'] = f'Error: {error_message}'
            data['steps'][0]['status'] = 'error'
            logger.error(f"Set error for session {self.session_id}: {error_message}")

# Utility function to clean up old sessions
def cleanup_old_sessions(max_age_hours=24):
    """Clean up progress tracker sessions older than max_age_hours"""
    with _progress_lock:
        current_time = time.time()
        sessions_to_remove = []
        
        for session_id, data in progress_tracker.items():
            # Check if session has timestamp and is old
            created_at = data.get('created_at', 0)
            age_hours = (current_time - created_at) / 3600
            
            if age_hours > max_age_hours:
                sessions_to_remove.append(session_id)
        
        # Remove old sessions
        for session_id in sessions_to_remove:
            del progress_tracker[session_id]
            logger.info(f"Cleaned up old progress session: {session_id}")
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old progress sessions")

# Function to force clean a specific session
def force_cleanup_session(session_id):
    """Force cleanup of a specific session"""
    with _progress_lock:
        if session_id in progress_tracker:
            del progress_tracker[session_id]
            logger.info(f"Force cleaned up progress session: {session_id}")
            return True
        return False