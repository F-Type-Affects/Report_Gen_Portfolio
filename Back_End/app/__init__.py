# app/__init__.py
# ==================
"""
Flask Application Factory
Creates and configures the Flask application with all blueprints and extensions
Preserves all original functionality from server.py
"""

from flask import Flask, render_template
from flask_session import Session
from redis import Redis
import logging
import os

def create_app(config_name=None):
    """
    Application factory function that creates and configures Flask app
    
    Args:
        config_name (str): Configuration environment name (optional)
        
    Returns:
        Flask: Configured Flask application instance
    """
    # Import configuration first
    from app.core.config import get_config
    config = get_config()
    
    # Configure logging BEFORE creating Flask app (preserve original behavior)
    config.configure_logging()
    
    # Initialize Flask app with proper template and static folders
    # Using the same configuration as original server.py
    app = Flask(__name__, 
                static_folder=config.STATIC_FOLDER,
                template_folder=config.TEMPLATE_FOLDER)
    
    # Configure Flask app (preserve original configuration)
    app.config.from_object(config)
    
    # Configure Redis session (preserve exact original configuration)
    app.config['SESSION_REDIS'] = Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT
    )
    
    # Set up sessions with Redis (preserve original behavior)
    Session(app)
    
    # Set up database (preserve original behavior)
    from .core.database import setup_database
    DATABASE_PATH = config.DATABASE_PATH
    setup_database(DATABASE_PATH)
    
    # Get logger (preserve original logging setup)
    logger = logging.getLogger(__name__)
    logger.info("Flask application initialized")
    
    # Register blueprints
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Log successful initialization
    logger.info("Application factory completed successfully")
    
    return app

def register_blueprints(app):
    """
    Register all application blueprints
    
    Args:
        app (Flask): Flask application instance
    """
    # Import blueprints
    from app.api.routes.auth_routes import auth_bp
    from app.api.routes.project_routes import project_bp
    from app.api.routes.ahj_routes import ahj_bp
    from app.api.routes.asce_routes import asce_bp
    from app.api.routes.soil_routes import soil_bp
    from app.api.routes.cover_letter_routes import cover_letter_bp
    from app.api.routes.workflow_routes import workflow_bp
    from app.api.routes.progress_routes import progress_bp
    
    # Register blueprints with URL prefixes
    # Auth routes have no prefix to maintain original URLs
    app.register_blueprint(auth_bp, url_prefix='/')
    
    # Other blueprints use prefixes for organization
    app.register_blueprint(project_bp, url_prefix='/project')
    app.register_blueprint(ahj_bp, url_prefix='/ahj') 
    app.register_blueprint(asce_bp, url_prefix='/asce')
    app.register_blueprint(soil_bp, url_prefix='/soil')
    app.register_blueprint(cover_letter_bp, url_prefix='/cover_letter')
    app.register_blueprint(workflow_bp, url_prefix='/workflow')
    app.register_blueprint(progress_bp, url_prefix='/api')
    
    app.logger.info("All blueprints registered successfully")

def register_error_handlers(app):
    """
    Register global error handlers
    
    Args:
        app (Flask): Flask application instance
    """
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        app.logger.warning(f"404 error: {error}")
        try:
            return render_template('error.html', 
                                 error_code=404, 
                                 error_message="Page not found"), 404
        except:
            # Fallback if error template doesn't exist
            return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        app.logger.error(f"500 error: {error}")
        try:
            return render_template('error.html', 
                                 error_code=500, 
                                 error_message="Internal server error"), 500
        except:
            # Fallback if error template doesn't exist
            return "Internal server error", 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all other exceptions"""
        app.logger.error(f"Unhandled exception: {e}")
        try:
            return render_template('error.html', 
                                 error_code=500, 
                                 error_message="An unexpected error occurred"), 500
        except:
            # Fallback if error template doesn't exist
            return "An unexpected error occurred", 500

# Create application instance for WSGI servers
# This preserves the ability to import 'app' directly
def get_app():
    """
    Get application instance for WSGI servers like Gunicorn
    
    Returns:
        Flask: Application instance
    """
    return create_app()