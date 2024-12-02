import http.client
import json
import requests
from urllib.parse import quote, urlparse
from .token_manager import fetch_access_token
from .database import get_sub_by_email
from .config import get_config
import logging
from flask import session

config = get_config()

logger = logging.getLogger(__name__)

def get_clients_by_name(client_name, selected_email):
    """
    Retrieves a list of clients matching the given client name

    Args:
        client_name (str): The client name to search for.
        selected_email (str): The email of the user initiating the request.

    Returns:
        dict: A dictionary containing client data retrieved from the API.
              Returns None if an error occurs or no clients are found.
    """
    # Step 1: Retrieve the user's unique identifier (sub) using their email.
    logger.info(f"Fetching clients by name: {client_name}")
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
        logger.error(f"No user found for email: {selected_email}")
        raise Exception("No user found for the given email")
    
    # Step 2: Set the base URL for the clients endpoint.
    client_base_url = config.CLIENT_BASE_URL  # Ensure this is defined in your config
    
    # Step 3: Fetch the access token required for API authentication.
    access_token = fetch_access_token(user_sub)
    
    # Step 4: Parse the base URL to extract components like hostname.
    parsed_url = urlparse(client_base_url)
    
    # Step 5: Construct the 'where' clause for the API query.
    where_clause = quote(f'"name=\'{client_name}\'"')
    
    # Step 6: Specify the fields we want to retrieve from the API.
    fields_clause = quote("id,name")
   
    # Step 7: Build the complete request path with query parameters.
    request_path = f"{client_base_url}?where={where_clause}&fields={fields_clause}"
    
    # Step 8: Set up the headers for the HTTP request, including the authorization token.
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }
    
    # Step 9: Establish a secure HTTPS connection to the API endpoint.
    conn = http.client.HTTPSConnection(parsed_url.hostname)

    try:
        # Step 10: Send a GET request to the API.
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
 
        # Step 11: Check the response status and handle accordingly.
        logger.debug(f"Response status: {res.status}")
        if res.status == 200:
            # Parse and return the JSON response.
            return json.loads(data.decode("utf-8"))
        elif res.status == 404:
            logger.warning(f"No clients found matching name: {client_name}")
            return None
        elif res.status == 204:
            logger.warning(f"No clients found matching name: {client_name}")
        else:
            return None
    except http.client.HTTPException as e:
        logging.error("HTTP error occurred: %s", e)
        logger.error(f"HTTP error occurred while fetching clients: {e}")
        return None
    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        logger.error(f"Unexpected response: {res.status} - {res.reason}")
        return None
    finally:
        conn.close()
        logger.debug("Connection closed.")

def fetch_manager_id(first_name, last_name, selected_email):
    logger.info(f"Fetching manager ID for employee: {first_name} {last_name}")
    user_sub = get_sub_by_email(selected_email)
    access_token = fetch_access_token(user_sub)
    base_url = config.EMPLOYEE_BASE_URL

    where_clause = quote(f'"firstName=\'{first_name}\' AND lastName=\'{last_name}\'"')
    fields_clause = quote("managerId")
    request_path = f"{base_url}?where={where_clause}&fields={fields_clause}"
    
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }

    conn = http.client.HTTPSConnection(urlparse(base_url).hostname)
    try:
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()

        logger.debug(f"Response status: {res.status}")
        if res.status == 200:
            response_data = json.loads(data.decode("utf-8"))
            return response_data[0]['managerId'] if response_data else None
        else:
            logger.warning(f"Manager not found for: {first_name} {last_name}")
            return None
    except Exception as e:
        logger.error(f"Error fetching manager ID: {e}")
        return None
    finally:
        conn.close()
        logger.debug("Connection closed.")

def get_employees(selected_email):
    logger.info(f"Fetching employees for user email: {selected_email}")
    user_sub = get_sub_by_email(selected_email)
    access_token = fetch_access_token(user_sub)
    base_url = config.EMPLOYEE_BASE_URL

    fields_clause = quote("firstName,lastName")
    request_path = f"{base_url}?fields={fields_clause}"
    
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }

    conn = http.client.HTTPSConnection(urlparse(base_url).hostname)
    try:
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        
        logger.debug(f"Response status: {res.status}")

        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            logger.warning(f"No employees found or failed request. Status: {res.status}")
            return None
    except Exception as e:
        logger.error(f"Error fetching employees: {e}")
        return None
    finally:
        conn.close()
        logger.debug("Connection closed.")

def send_create_project_request(project_details):
    logger.info(f"Sending create project request for project: {project_details.get('name', 'Unknown')}")
    access_token = fetch_access_token(session.get('selected_email'))
    base_url = config.PROJECT_BASE_URL
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }
    conn = http.client.HTTPSConnection(urlparse(base_url).hostname)
    try:
        payload = json.dumps(project_details)
        logger.debug(f"Request payload: {payload}")
        conn.request("POST", base_url, body=payload, headers=headers)
        res = conn.request
        logger.debug(f"Response status: {res.status}")
        return res
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return None
    finally:
        conn.close()
        logger.debug("Connection closed.")
