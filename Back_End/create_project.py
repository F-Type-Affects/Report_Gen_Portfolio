import http.client
import json
import requests
from urllib.parse import quote, urlparse
from .token_manager import fetch_access_token
from .database import get_sub_by_email
from . import config
import logging

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
    # We use URL encoding to handle special characters in the client name.
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
            print("No clients found matching the given name.")
            return None
        else:
            # Handle other HTTP errors.
            error_message = f"API request failed with status {res.status}: {res.reason}"
            print(error_message)
            return None
    except http.client.HTTPException as e:
        logging.error("HTTP error occurred: %s", e)
        return None
    except Exception as e:
        logging.error("An unexpected error occurred: %s", e)
        return None
    finally:
        conn.close()


def get_managers_list(selected_email):
    """
    Fetch a list of managers using the employee API.
    """
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
        raise Exception("No user found for the given email")

    # Use the employee API to get list of employees
    employees = get_employees(selected_email)
    # Filter employees to get managers (assuming managers have a specific role or attribute)
    managers = [emp for emp in employees if emp.get('isManager', False)]
    return managers

def get_employees(selected_email):
    """
    Fetch a list of employees from the BQE Core API.
    """
    user_sub = get_sub_by_email(selected_email)
    access_token = fetch_access_token(user_sub)

    employee_base_url = config.EMPLOYEE_BASE_URL  # Ensure this is defined in your config
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }

    response = requests.get(employee_base_url, headers=headers)
    if response.status_code == 200:
        employee_data = response.json()
        return employee_data.get('items', [])
    else:
        logging.error(f"Failed to retrieve employees: {response.status_code} - {response.text}")
        return []

def create_project_in_bqe(project_code, contract_type, project_name, project_type, project_address, email, phone_number, client_id, manager_id, selected_email):
    """
    Create a new project in BQE Core using the provided details.
    """
    user_sub = get_sub_by_email(selected_email)
    access_token = fetch_access_token(user_sub)

    project_base_url = config.PROJECT_BASE_URL  # Ensure this is defined in your config
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
        'Authorization': f"Bearer {access_token}"
    }

    # Construct the project data payload
    project_data = {
        "code": project_code,
        "contractType": contract_type,
        "name": project_name,
        "projectType": project_type,
        "address": project_address,
        "email": email,
        "phoneNumber": phone_number,
        "clientId": client_id,
        "managerId": manager_id
    }

    # Make the API call to create the project
    response = requests.post(project_base_url, json=project_data, headers=headers)
    if response.status_code == 201:
        return True
    else:
        logging.error(f"Failed to create project: {response.status_code} - {response.text}")
        return False
