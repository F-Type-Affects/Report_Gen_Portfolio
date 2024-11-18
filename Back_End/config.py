# import libraries
import os
from dotenv import load_dotenv

# load the enviornment variables
load_dotenv()

# enviornment variables
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
AUTH_BASE_URL = os.getenv('AUTH_BASE_URL')
CALL_BACK_URI = os.getenv('CALL_BACK_URI')
TOKEN_BASE_URL = os.getenv('TOKEN_BASE_URL')
DATABASE_PATH = os.getenv('DATABASE_PATH')
BASE_URL = os.getenv('BASE_URL')
PROJECT_BASE_URL = os.getenv('PROJECT_BASE_URL')
CLIENT_BASE_URL = os.getenv('CLIENT_BASE_URL')
EMPLOYEE_BASE_URL = os.getenv('EMPLOYEE_BASE_URL')
USER_INFO_BASE_URL = os.getenv('USER_INFO_BASE_URL')
SCOPE = os.getenv('SCOPE')
REPORT_DIRECTORY = os.getenv('REPORT_DIRECTORY')
APP_KEY  = os.getenv('APP_KEY')
LOGIN = os.getenv('AHJ_LOGIN')
PW = os.getenv('AHJ_P')
AHJ_LINK = os.getenv('AHJ_INFO')
AMEND_LINK = os.getenv('AMENDMENT_LINK')
BING_KEY = os.getenv('BING_API_KEY')
BING_ENDPOINT = os.getenv('BING_API_ENDPOINT')
COVER_LETTER_TEMPLATE_PATH = os.getenv('COVER_LETTER_TEMPLATE_PATH')
COVER_LETTER_OUTPUT_DIR = os.getenv('COVER_LETTER_OUTPUT_DIR')
