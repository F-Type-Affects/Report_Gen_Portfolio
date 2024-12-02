import http.client
import json
import logging
from urllib.parse import urlparse, quote
from .config import get_config
from Back_End.token_manager import fetch_access_token
from Back_End.database import get_sub_by_email

config = get_config()

logger = logging.getLogger(__name__)

def get_project_address_by_code(project_code, selected_email):
    """
    Retrieves a list of projects with given code using the users email
    Args: 
        project_code(str): the project code to search
        selected_email(str): the email of the user
    Returns: 
        dict: project data retrieved from API
    """
    logger.info(f"Fetching project address for code: {project_code}, email: {selected_email}")
    # get user sub
    user_sub = get_sub_by_email(selected_email)
    if not user_sub:
        logger.error("No user found for the given email.")
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
        logger.debug(f"Sending GET request to {request_path}")
        conn.request("GET", request_path, headers=headers)
        res = conn.getresponse()
        data = res.read()
        
        logger.debug(f"Response status: {res.status}")
        logger.debug(f"Response data: {data.decode('utf-8')}")
        
        if res.status == 200:
            logger.info("Project data retrieved successfully.")
            return json.loads(data.decode("utf-8"))
        else:
            logger.warning(f"Failed to retrieve project data. Status code: {res.status}")
            return None
    except http.client.HTTPException as e:
        logger.error(f"HTTP error occurred while fetching project data: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred while fetching project data: {e}")
        return None
    finally:
        conn.close()
    
def update_project_address_in_bqe(project_data, address, selected_email):
        """Update the project address via the BQE API."""
        logger.info(f"Updating project address for project ID: {project_data['id']}, email: {selected_email}")
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
        url = f"{project_base_url}{project_data['id']}"

        # Prepare headers
        user_sub = get_sub_by_email(selected_email)
        if not user_sub:
            logger.error("No user found for the given email.")
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
            logger.debug(f"Sending PUT request to {url} with payload: {payload_json}")
            conn.request("PUT", parsed_url.path, body=payload_json, headers=headers)
            res = conn.getresponse()
            data = res.read()
            
            logger.debug(f"Response status: {res.status}")
            logger.debug(f"Response data: {data.decode('utf-8')}")
        
            if res.status == 200:
                logger.info("Project address updated successfully.")
            else:
                logger.warning(f"Failed to update project address. Status code: {res.status}")
                logger.warning(f"Response: {data.decode('utf-8')}")
        except http.client.HTTPException as e:
            logger.error(f"HTTP error occurred while updating project address: {e}")
        except Exception as e:
            logger.error(f"Unexpected error occurred while updating project address: {e}")
        finally:
            conn.close()


