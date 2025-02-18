import os
from dotenv import load_dotenv
from datetime import timedelta
import logging

# Load the environment variables
load_dotenv()

# Base configuration class
class Config:
    # shared configurations
    CLIENT_ID = os.getenv('CLIENT_ID')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    AUTH_BASE_URL = os.getenv('AUTH_BASE_URL')
    CALL_BACK_URI = os.getenv('CALL_BACK_URI')
    TOKEN_BASE_URL = os.getenv('TOKEN_BASE_URL')
    BASE_URL = os.getenv('BASE_URL')
    PROJECT_BASE_URL = os.getenv('PROJECT_BASE_URL')
    CLIENT_BASE_URL = os.getenv('CLIENT_BASE_URL')
    EMPLOYEE_BASE_URL = os.getenv('EMPLOYEE_BASE_URL')
    USER_INFO_BASE_URL = os.getenv('USER_INFO_BASE_URL')
    SCOPE = os.getenv('SCOPE')
    SECRET_KEY = os.getenv('SECRET_KEY')
    LOGIN = os.getenv('AHJ_LOGIN')
    PW = os.getenv('AHJ_P')
    AHJ_LINK = os.getenv('AHJ_INFO')
    AMEND_LINK = os.getenv('AMENDMENT_LINK')
    BING_KEY = os.getenv('BING_API_KEY')
    BING_ENDPOINT = os.getenv('BING_API_ENDPOINT')
    
    # session configurations
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')  # Default to production
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'sml_report_gen:'
    REDIS_HOST = '127.0.0.1'
    REDIS_PORT = 6379
    
    @classmethod
    def configure_logging(cls):
        """Set up logging based on env"""
        logging.basicConfig(
            level=cls.LOG_LEVEL,
            format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )

# Development configuration
class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    REDIS_HOST = '127.0.0.1'
    STATIC_FOLDER = r"C:\Users\fstranathan\Desktop\SML_Reports_Test\Front_End_Web\static"
    TEMPLATE_FOLDER = r"C:\Users\fstranathan\Desktop\SML_Reports_Test\Front_End_Web\templates"
    DATABASE_PATH = os.getenv('DATABASE_PATH')
    REPORT_DIRECTORY = os.getenv('REPORT_DIRECTORY')
    POOL_DIRECTORY = os.getenv('POOL_DIRECTORY')
    COVER_LETTER_TEMPLATE_PATH = os.getenv('COVER_LETTER_TEMPLATE_PATH')
    COVER_LETTER_OUTPUT_DIR = os.getenv('COVER_LETTER_OUTPUT_DIR')
    COVER_LETTER_POOLS_OUTPUT = os.getenv('COVER_LETTER_POOLS_OUTPUT')
    # logging settings
    LOG_LEVEL = logging.DEBUG
    DEBUG = True
    
# Production configuration
class ProductionConfig(Config):
    DEBUG = False
    LOG_LEVEL = logging.WARNING
    REDIS_HOST = '127.0.0.1'
    STATIC_FOLDER = "/home/frank/SML_Reports_Test/SML_Report_Gen/Front_End_Web/static"
    TEMPLATE_FOLDER = "/home/frank/SML_Reports_Test/SML_Report_Gen/Front_End_Web/templates"
    DATABASE_PATH = os.getenv('DATABASE_PATH')
    REPORT_DIRECTORY = os.getenv('REPORT_DIRECTORY')
    POOL_DIRECTORY = os.getenv('POOL_DIRECTORY')
    COVER_LETTER_TEMPLATE_PATH = os.getenv('COVER_LETTER_TEMPLATE_PATH')
    COVER_LETTER_OUTPUT_DIR = os.getenv('COVER_LETTER_OUTPUT_DIR')
    COVER_LETTER_POOLS_OUTPUT = os.getenv('COVER_LETTER_POOLS_OUTPUT')
    
    # logging settings
    LOG_LEVEL = min(logging.WARNING, logging.INFO)
    DEBUG = False
    
# Function to get the correct configuration
def get_config():
    env = os.getenv('FLASK_ENV', 'production')
    if env == 'development':
        return DevelopmentConfig
    return ProductionConfig
