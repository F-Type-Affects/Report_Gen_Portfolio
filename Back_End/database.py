import sqlite3
import logging
import os
from .config import get_config

config = get_config()

DATABASE_PATH = config.DATABASE_PATH

logger = logging.getLogger(__name__)

def setup_database(db_path):
    """ Sets up the database only if it doesn't already exist with the expected schema. """
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                sub TEXT PRIMARY KEY,
                email TEXT,
                first_name TEXT,
                last_name TEXT,
                user_id TEXT,
                id_token TEXT,
                access_token TEXT,
                expires_in INTEGER,
                token_type TEXT,
                refresh_token TEXT,
                refresh_token_expires_in INTEGER
            );
        ''')
        conn.commit()
        conn.close()
        logger.info("Database created and initialized with new schema")
    else:
        logger.info(f"Database already exists")

def insert_token_data(sub, email, first_name, last_name, user_id, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in):
    """
    Inserts a new set of token data into the database.
    """
    query = '''
        INSERT INTO tokens (sub, email, first_name, last_name, user_id, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    params = (sub, email, first_name, last_name, user_id, id_token, access_token, expires_in, token_type, refresh_token, refresh_token_expires_in)
    execute_query(query, params)
    logger.debug("New token data with user info inserted")


def update_token_data(sub, access_token, expires_in, refresh_token, refresh_token_expires_in):
    """
    Updates token data in the database when a refresh occurs.
    """
    query = '''
        UPDATE tokens
        SET access_token = ?, expires_in = ?, refresh_token = ?, refresh_token_expires_in = ?
        WHERE sub = ?
    '''
    params = (access_token, expires_in, refresh_token, refresh_token_expires_in, sub)
    execute_query(query, params)
    logger.debug(f"Token data updated ")

def execute_query(query, params=None, is_select=False):
    """
    Execute a given SQL query on the database with parameters and handle exceptions.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if is_select:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = None
            
        conn.close()
        return result
    except sqlite3.Error as e:
        logger.error(f"Database error: {e} with query: {query}")
        raise

def get_all_emails():
    """
    Retrieves all emails from the database
    Returns: list of emails
    """
    query = "SELECT email FROM tokens"
    result = execute_query(query, is_select=True)
    if result:
        return [email[0] for email in result]
    else:
        return []

    
def get_sub_by_email(email):
    """
    Retrieves the sub associated with the given email.
    Args: email (str)
    Returns: sub (str)
    """
    query = "SELECT sub FROM tokens WHERE email = ?"
    result = execute_query(query, (email,), is_select=True)
    if result:
        return result[0][0]
    else:
        return None

def get_user_details_by_email(email):
    """
    Retrieves the first name and last name of the user associated with the given email.

    Args:
        email (str): The user's email address.

    Returns:
        dict: A dictionary containing 'first_name' and 'last_name', or None if not found.
    """
    query = "SELECT first_name, last_name FROM tokens WHERE email = ?"
    try:
        result = execute_query(query, (email,), is_select=True)
        if result:
            row = result[0]  # fetchone equivalent
            return {'first_name': row[0], 'last_name': row[1]}
        else:
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve user details for email {email}: {e}")
        return None
   
def get_all_tokens_data():
    """
    Retrieves all tokens data stored in the database.
    Returns:
        List of tuples containing token data.
    """
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tokens")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except sqlite3.Error as e:
        print(f"Failed to retrieve token data: {e}")
        return []

def print_all_tokens():
    """
    Fetches and logs all records from the tokens table for verification purposes.
    """
    try:
        tokens = get_all_tokens_data()
        if not tokens:
            logger.info("No tokens found in the database.")
            return
        logger.info("Current contents of the tokens table:")
        for token in tokens:
            # token is a tuple corresponding to the columns in the table
            (
                sub,
                email,
                first_name,
                last_name,
                user_id,
                id_token,
                access_token,
                expires_in,
                token_type,
                refresh_token,
                refresh_token_expires_in
            ) = token
            logger.info(f"Sub: {sub}, Email: {email}, First Name: {first_name}, Last Name: {last_name}, User ID: {user_id}, "
                        f"ID Token: {id_token}, Access Token: {access_token}, Expires In: {expires_in}, "
                        f"Token Type: {token_type}, Refresh Token: {refresh_token}, "
                        f"Refresh Token Expires In: {refresh_token_expires_in}")
    except Exception as e:
        logger.error(f"Error printing tokens: {e}")