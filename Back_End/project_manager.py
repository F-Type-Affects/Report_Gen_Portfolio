import http.client
import os
import json
from urllib.parse import urlparse, quote
import requests
import logging
from .token_manager import refresh_access_token, get_valid_access_token, fetch_access_token, fetch_access_token_by_email
from .database import get_sub_by_email
from . import config

# Configure logging
logging.basicConfig(level=logging.WARNING)
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
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
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
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            return None
    except http.client.HTTPException as e:
        print("HTTP error occurred:", e)
    finally:
        conn.close()

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
        return client_id
    except (IndexError, KeyError, TypeError) as e:
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
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
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
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            return None
    except http.client.HTTPException as e:
        print("HTTP error occurred: ", e)
    finally:
        conn.close()

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
        return address_details

    except Exception as e:
        print(f"Error extracting project address: {e}")
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
        
        return project_details
    except Exception as e:
        print(f"Error extracting project details: {e}")
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
        return address_details
    
    except Exception as e:
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
        
        return client_details
    except Exception as e:
        print(f"Error extracting client details: {e}")
        return {}
    