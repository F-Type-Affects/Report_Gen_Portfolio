# Back_End/server.py
# ===================
"""
Main application entry point
Refactored from original 1800-line server.py to use application factory pattern
Preserves all original functionality while enabling modular architecture
"""

import os
import sys
import logging

# Add the current directory to Python path for imports (preserve original behavior)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

def main():
    """
    Main application entry point
    Creates Flask app and runs development server
    Preserves exact original server.py behavior
    """
    try:
        # Import and create Flask application using factory pattern
        from app import create_app
        app = create_app()
        
        # Get logger (preserve original logging)
        logger = logging.getLogger(__name__)
        logger.info("Starting Flask application with preserved functionality...")
        
        # Run the application with EXACT original configuration
        if __name__ == '__main__':
            # Preserve original development server configuration
            app.run(
                host='127.0.0.1',     # Same as original
                port=8888,            # Same as original  
                debug=True,           # Same as original
                threaded=True         # Enable threading for background tasks
            )
        
        return app
        
    except Exception as e:
        print(f"Failed to start application: {str(e)}")
        logging.error(f"Application startup failed: {str(e)}")
        sys.exit(1)

# Create app instance for WSGI servers (like Gunicorn)
# This preserves the ability to import the app instance directly
try:
    from app import create_app
    app = create_app()
except Exception as e:
    print(f"Failed to create app instance: {str(e)}")
    app = None

# Preserve original entry point behavior
if __name__ == '__main__':
    main()