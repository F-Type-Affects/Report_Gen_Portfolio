# app/api/routes/progress_routes.py
# ===================================
"""
Progress tracking routes - ENHANCED VERSION WITH CLEANUP
Handles real-time progress updates via Server-Sent Events (SSE)
"""

from flask import Blueprint, Response, jsonify, request
import json
import time
import logging
import uuid
from threading import Thread

# Create blueprint
progress_bp = Blueprint('progress', __name__)

# Get logger
logger = logging.getLogger(__name__)

# Global progress tracker - MAKE SURE THIS IS ACCESSIBLE
progress_tracker = {}

# Test route to verify blueprint registration
@progress_bp.route('/progress/test')
def test_progress():
    """Test route to verify the progress blueprint is working"""
    return jsonify({
        'status': 'success',
        'message': 'Progress blueprint is working correctly',
        'blueprint': 'progress',
        'active_sessions': list(progress_tracker.keys()),
        'session_count': len(progress_tracker)
    })

# Debug route to inspect progress data
@progress_bp.route('/progress/debug/<session_id>')
def debug_progress(session_id):
    """Debug route to manually test progress tracking"""
    # Clean up the session first if it exists
    if session_id in progress_tracker:
        del progress_tracker[session_id]
    
    # Add fresh test data
    progress_tracker[session_id] = {
        'overall_progress': 0,  # Start at 0
        'current_step': 0,
        'steps': [
            {'name': 'Test Step', 'status': 'pending', 'progress': 0}
        ],
        'status': 'starting',
        'message': 'Debug test initializing...',
        'error': None,
        'completed': False,
        'created_at': time.time()
    }
    
    return jsonify({
        'status': 'success',
        'message': f'Debug data added for session {session_id}',
        'data': progress_tracker[session_id]
    })

# New cleanup route
@progress_bp.route('/progress/cleanup/<session_id>', methods=['POST'])
def cleanup_session(session_id):
    """Manually cleanup a specific session"""
    if session_id in progress_tracker:
        del progress_tracker[session_id]
        logger.info(f"Manually cleaned up progress session: {session_id}")
        return jsonify({
            'status': 'success',
            'message': f'Session {session_id} cleaned up successfully'
        })
    else:
        return jsonify({
            'status': 'info',
            'message': f'Session {session_id} was not found in tracker'
        })

# New cleanup all route
@progress_bp.route('/progress/cleanup-all', methods=['POST'])
def cleanup_all_sessions():
    """Cleanup all progress sessions"""
    session_count = len(progress_tracker)
    progress_tracker.clear()
    logger.info(f"Manually cleaned up all {session_count} progress sessions")
    return jsonify({
        'status': 'success',
        'message': f'Cleaned up {session_count} sessions'
    })

# Enhanced progress stream with better error handling
@progress_bp.route('/progress/<session_id>')
def progress_stream(session_id):
    """
    Server-Sent Events endpoint for real-time progress updates - ENHANCED VERSION
    
    This endpoint provides real-time progress updates for long-running operations
    using Server-Sent Events (SSE). The JavaScript frontend connects to this
    endpoint to receive live progress updates.
    
    Args:
        session_id (str): Unique session ID for the progress tracking
        
    Returns:
        Response: SSE stream with progress updates
    """
    def generate_progress():
        try:
            # Send initial connection confirmation with debug info
            initial_data = {
                'status': 'connected', 
                'session_id': session_id, 
                'tracker_keys': list(progress_tracker.keys()),
                'session_exists': session_id in progress_tracker,
                'timestamp': time.time()
            }
            yield f"data: {json.dumps(initial_data)}\n\n"
            
            max_iterations = 600  # 10 minutes max
            iteration = 0
            last_data_hash = None  # To avoid sending duplicate data
            
            while iteration < max_iterations:
                try:
                    if session_id in progress_tracker:
                        data = progress_tracker[session_id]
                        
                        # Create a simple hash to avoid sending duplicate data
                        current_hash = f"{data.get('overall_progress', 0)}-{data.get('status', 'unknown')}-{data.get('current_step', 0)}"
                        
                        # Only send if data has changed or every 10th iteration
                        if current_hash != last_data_hash or iteration % 10 == 0:
                            # Add debugging info to data
                            data_with_debug = data.copy()
                            data_with_debug['debug_info'] = {
                                'iteration': iteration,
                                'timestamp': time.time(),
                                'data_hash': current_hash
                            }
                            
                            logger.debug(f"Sending progress data for {session_id}: overall={data.get('overall_progress', 'N/A')}, status={data.get('status', 'N/A')}")
                            yield f"data: {json.dumps(data_with_debug)}\n\n"
                            last_data_hash = current_hash
                        
                        # Check if process is completed or has an error
                        if data.get('completed') or data.get('status') == 'error':
                            logger.info(f"Progress tracking completed for session: {session_id}")
                            break
                    else:
                        # Send heartbeat to keep connection alive, but less frequently
                        if iteration % 5 == 0:  # Every 2.5 seconds instead of every 0.5 seconds
                            heartbeat_data = {
                                'status': 'waiting', 
                                'iteration': iteration, 
                                'session_id': session_id,
                                'tracker_keys': list(progress_tracker.keys()),
                                'message': f'Waiting for progress data... (iteration {iteration})',
                                'timestamp': time.time()
                            }
                            yield f"data: {json.dumps(heartbeat_data)}\n\n"
                    
                    time.sleep(0.5)  # Send updates every 500ms
                    iteration += 1
                    
                except Exception as e:
                    logger.error(f"Error in progress stream iteration {iteration}: {str(e)}")
                    yield f"data: {json.dumps({'status': 'error', 'message': str(e), 'session_id': session_id, 'iteration': iteration})}\n\n"
                    break
            
            # Send final message if max iterations reached
            if iteration >= max_iterations:
                logger.warning(f"Progress tracking timeout for session: {session_id}")
                yield f"data: {json.dumps({'status': 'timeout', 'message': 'Progress tracking timeout', 'session_id': session_id})}\n\n"
            
        except GeneratorExit:
            logger.info(f"Progress stream closed for session: {session_id}")
        except Exception as e:
            logger.error(f"Critical error in progress stream: {str(e)}")
            yield f"data: {json.dumps({'status': 'critical_error', 'message': str(e), 'session_id': session_id})}\n\n"
    
    return Response(
        generate_progress(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering
        }
    )

# New route to get current session status
@progress_bp.route('/progress/status/<session_id>')
def get_session_status(session_id):
    """Get current status of a progress session"""
    if session_id in progress_tracker:
        data = progress_tracker[session_id]
        return jsonify({
            'status': 'found',
            'session_id': session_id,
            'progress_data': data
        })
    else:
        return jsonify({
            'status': 'not_found',
            'session_id': session_id,
            'message': 'Session not found in progress tracker',
            'active_sessions': list(progress_tracker.keys())
        })