import http.client
import os
import json
from urllib.parse import urlparse, quote
import requests
import logging
from app.auth.token_manager import refresh_access_token, get_valid_access_token, fetch_access_token, fetch_access_token_by_email
from app.core.database import get_sub_by_email
from app.core.config import get_config

config = get_config()

logger = logging.getLogger(__name__)

# get project base URL
client_base_url = config.CLIENT_BASE_URL

# retrieve a list of projects with the associated project code
def get_project_by_code(project_code, selected_email):
    """
    Retrieves a list of projects with given code using the users email
    Args: 
        project_code(str): the project code to search
        selected_email(str): the email of the user
    Returns: 
        dict: project data retrieved from API
    """
    # get user sub
    logger.info(f"Fetching project with code: {project_code} for user: {selected_email}")
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
        logger.error(f"No user found for the given email: {selected_email}")
        raise Exception("No user found for the given email")
    
    project_base_url = config.PROJECT_BASE_URL
    
    access_token = fetch_access_token(user_sub)
    
    parsed_url = urlparse(project_base_url)
    where_clause = quote(f'"code=\'{project_code}\'"')  # URL encode the where clause
    fields_clause = quote("code,name,address,purchaseOrderNumber,billingContact,clientId")
    request_path = f"{project_base_url}?where={where_clause}&fields={fields_clause}"
    
    headers = {
        'accept': "application/json",
        'content-type': "application/json",
        'authorization': f"Bearer {access_token}"
    }

    conn = http.client.HTTPSConnection(parsed_url.hostname)

    try:
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        logger.debug(f"Response status: {res.status}")
        logger.debug(f"Get Project By Code data returned: {data.decode('utf-8')}")
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            logger.warning(f"Failed to fetch project. Status: {res.status}")
            return None
    except http.client.HTTPException as e:
        logger.error(f"HTTP error occurred while fetching project: {e}")
    finally:
        conn.close()
        logger.debug("Connection closed.")

# extract the client id number from the project object list in order to retrieve the correct client object
def extract_client_id(project_data):
    """
    Extracts the client ID from the project data.

    Args:
    project_data (dict): The JSON object representing the project, as returned by get_project_by_code.

    Returns:
    str: The extracted client ID or None if the ID cannot be found.
    """
    try:
        # take first item in list
        # Extract client id from first item
        client_id = project_data[0]['clientId']
        logger.info(f"Extracted client ID: {client_id}")
        return client_id
    except (IndexError, KeyError, TypeError) as e:
        logger.error(f"Error extracting client ID: {e}")
        return None

# Retrieve Client Object from BQE Endpoint which contains client name and address        
def get_client_by_id(client_id, selected_email):
    """
    Retrieves the client information using the client id extracted from the project details
    Args:
        client_id(str): clients unique identifer
        selected_email: users email
    Returns:
        dict: client information retrieved from API
    """
    logger.info(f"Fetching client with ID: {client_id}")
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
        logger.error(f"No user found for the given email: {selected_email}")
        raise Exception("No user found for the given email")
    
    client_base_url = config.CLIENT_BASE_URL

    access_token = fetch_access_token(user_sub)

    parsed_url = urlparse(client_base_url)
    where_clause = quote(f'"id=\'{client_id}\'"')  # URL encode the where clause
    fields_clause = quote("name, address")
    request_path = f"{client_base_url}?where={where_clause}&fields={fields_clause}"
    
    
    headers = {
        'accept': "application/json",
        'content-type': "application/json",
        'authorization': f"Bearer {access_token}"
    }
    
    conn = http.client.HTTPSConnection(parsed_url.hostname)
    
    try:
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        logger.debug(f"Response status: {res.status}")
        logger.debug(f"Get Client By ID data returned: {data.decode('utf-8')}")
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            logger.warning(f"Failed to fetch client. Status: {res.status}")
            return None
    except http.client.HTTPException as e:
        logger.error(f"HTTP error occurred while fetching client: {e}")
    finally:
        conn.close()
        logger.debug("Connection closed.")

# extract the specefic project address from the list of projects
def extract_project_address(project_data):
    """
    Extracts the project address from the project data.

    Args:
    project_data (dict): The JSON object representing the project, as returned by get_project_by_code.

    Returns:
    dict: A dictionary containing the address components.
    """
    try:
        single_project = project_data[0]
        address = single_project['address'][0]
     
        address_details = {
            'Street1': address.get('street1', ''),
            'Street2': address.get('street2', ''),
            'City': address.get('city', ''),
            'State': address.get('state', ''),
            'Zip': address.get('zip', ''),
        }
        logger.info(f"Extracted project address: {address_details}")
        return address_details

    except Exception as e:
        logger.error(f"Error extracting project address: {e}")
        return {}

# extract the specefic project details from the list
def extract_project_details(project_data):
    """
    Extracts the project details from the project data.

    Args:
    project_data (dict): The JSON object representing the project, as returned by get_project_by_code.

    Returns:
    dict: A dictionary containing the project details.
    """
    try:
        project_data = project_data[0]

        project_details = {
            'code': project_data.get('code', ''),
            'Project Name': project_data.get('name', ''),
            'Project PO#': project_data.get('purchaseOrderNumber', ''),
            'Billing Contact': project_data.get('billingContact', ''),
        }
        logger.info(f"Extracted project details: {project_details}")
        return project_details
    except Exception as e:
        logger.error(f"Error extracting project details: {e}")
        return {}

# extract the client address
def extract_client_address(client_data):
    """
    Extracts the client address from the project data.

    Args:
    project_data (dict): The JSON object representing the client, as returned by get_client_by_code.

    Returns:
    dict: A dictionary containing the address components.
    """
    
    try:
        address = client_data[0]['address']
        
        address_details = {
            'Street1': address.get('street1', ''),
            'Street2': address.get('street2', ''),
            'City': address.get('city', ''),
            'State': address.get('state', ''),
            'Zip': address.get('zip', ''),
        }
        logger.info(f"Extracted client address: {address_details}")
        return address_details
    
    except Exception as e:
        logger.error(f"Error extracting client address: {e}")
        return {}

# extract the relevant client details
def extract_client_details(client_data):
    """
    Extracts the client details from the project data.

    Args:
    project_data (dict): The JSON object representing the client, as returned by get_client_by_code.

    Returns:
    dict: A dictionary containing the project details.
    """
    try:
        details = client_data[0]

        client_details = {
            'Client Name': details.get('name', ''),
        }
        logger.info(f"Extracted client details: {client_details}")
        return client_details
    except Exception as e:
        logger.error(f"Error extracting client details: {e}")
        return {}
    