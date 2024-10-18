import http.client
import json
from urllib.parse import urlparse, quote
from Back_End import config
from Back_End.token_manager import fetch_access_token
from Back_End.database import get_sub_by_email

def get_project_address_by_code(project_code, selected_email):
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
    fields_clause = quote("code,id,clientId,managerId,name,type,contractType,address,memo")
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
        
        # Print the raw data for debugging
        print("Raw project data from API: ", data.decode("utf-8"))
        
        if res.status == 200:
            return json.loads(data.decode("utf-8"))
        else:
            return None
    except http.client.HTTPException as e:
        print("HTTP error occurred:", e)
    finally:
        conn.close()
    
def update_project_address_in_bqe(project_data, address, selected_email):
        """Update the project address via the BQE API."""
    
        project_id = project_data['id']
    
        # Construct the project payload with all necessary fields
        payload = {
            "id": project_data["id"],
            "code": project_data["code"],
            "name": project_data["name"],
            "type": project_data.get("type", None),
            "contractType": project_data.get("contractType", None),
            "clientId": project_data["clientId"],
            "managerId": project_data["managerId"],
            "memo": project_data.get("memo", ""),
            "address": [
                {
                    "street1": address["street1"],
                    "street2": address["street2"],
                    "city": address["city"],
                    "state": address["state"],
                    "zip": address["zip"]
                }
            ]
        }

        # Prepare the API URL
        project_base_url = config.PROJECT_BASE_URL
        url = f"{project_base_url}{project_id}"

        # Prepare headers
        user_sub = get_sub_by_email(selected_email)
        if not user_sub:
            raise Exception("No user found for the given email")
    
        access_token = fetch_access_token(user_sub)

        headers = {
            'accept': "application/json",
            'content-type': "application/json",
            'authorization': f"Bearer {access_token}"
        }

        # Convert the payload to JSON format
        payload_json = json.dumps(payload)
    
        # Parse the URL and send the PUT request
        parsed_url = urlparse(url)
        conn = http.client.HTTPSConnection(parsed_url.hostname)

        try:
            print(f"Sending request to: {url}")
            conn.request("PUT", parsed_url.path, body=payload_json, headers=headers)
            res = conn.getresponse()
            data = res.read()
        
            if res.status == 200:
                print("Address updated successfully.")
            else:
                print(f"Failed to update address: {res.status}")
                print(data.decode("utf-8"))
        finally:
            conn.close()


