import http.client
import json
import requests
from urllib.parse import quote, urlparse
from .token_manager import fetch_access_token
from .database import get_sub_by_email
from . import config
import logging
from flask import session

logging.basicConfig(level=logging.info)

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
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
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
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
 
        # Step 11: Check the response status and handle accordingly.
        if res.status == 200:
            # Parse and return the JSON response.
            return json.loads(data.decode("utf-8"))
        elif res.status == 404:
            # Handle case where no clients are found.
            return None
        elif res.status == 204:
            return None
        else:
            return None
    except http.client.HTTPException as e:
        logging.error("HTTP error occurred: %s", e)
        return None
    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        return None
    finally:
        conn.close()

def fetch_manager_id(first_name, last_name, selected_email):
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
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()

        if res.status == 200:
            response_data = json.loads(data.decode("utf-8"))
            return response_data[0]['managerId'] if response_data else None
        else:
            return None
    finally:
        conn.close()

def get_employees(selected_email):
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
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        
        # Log the response status and reason
        print(f"Response status: {res.status}")
        print(f"Response reason: {res.reason}")
        
        # Decode and print raw data
        print(f"Raw data received: {data}")

        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            return None
    finally:
        conn.close()

def send_create_project_request(project_details):
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
        conn.request("POST", base_url, body=payload, headers=headers)
        return conn.getresponse()
    finally:
        conn.close()
