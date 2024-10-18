import logging
import time
import requests
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from . import config

logger = logging.getLogger(__name__)

# create realistic user angents to help avoid rate limiting
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.864.48 Safari/537.36 Edg/91.0.864.48",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.55"
]

# Initialize web driver for Selenium to search AHJ registry
def init_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--start-fullscreen")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# Function to search AHJ registry
def search_ahj_registry(address):
    email = config.LOGIN
    pw = config.PW
    driver = init_driver()
    driver.get('https://ahjregistry.myorangebutton.com/#/ahj-search')

    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login-btn"]')))
    driver.find_element(By.XPATH, '//*[@id="login-btn"]').click()

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[1]/input')))
    driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[1]/input').send_keys(email)
    driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[2]/input').send_keys(pw)
    driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/button').click()

    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button')))
    driver.find_element(By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button').click()

    WebDriverWait(driver, 20).until_not(EC.presence_of_element_located((By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button')))
    search_box = driver.find_element(By.XPATH, '//*[@id="search-bar-input"]')
    search_box.send_keys(address)
    search_box.send_keys(Keys.RETURN)

    WebDriverWait(driver, 20).until_not(EC.text_to_be_present_in_element((By.XPATH, '/html/body/div/div/div[3]/div[2]/div/table/tbody'), 'Loading...'))
    table = driver.find_element(By.XPATH, '/html/body/div/div/div[3]/div[2]/div/table')
    rows = table.find_elements(By.TAG_NAME, 'tr')

    table_data = []
    for row in rows:
        cols = row.find_elements(By.TAG_NAME, 'td')
        if len(cols) > 0:
            table_data.append([col.text for col in cols])
    driver.quit()

    # Convert table data to a DataFrame and return as JSON serializable
    df = pd.DataFrame(table_data, columns=['AHJ Code', 'AHJ Name', 'County', 'Building Code', 'Electric Code', 'Fire Code', 'Residential Code', 'Wind Code', 'More Info'])
    return df.to_dict(orient='records')

# Function to perform Bing search with exponential backoff and PDF filter
def perform_bing_search(query, retries=5):
    bing_api_url = f"{config.BING_ENDPOINT}v7.0/search"  # Bing Search API endpoint
    api_key = config.BING_KEY  # Your Bing API key from Azure
    delay = 1  # Start with a 1-second delay
    max_delay = 60  # Cap delay to avoid long waits

    # Create a custom session for making API calls
    session = requests.Session()
    session.headers.update({
        "Ocp-Apim-Subscription-Key": api_key  # Bing API key
    })

    # Append the PDF filetype filter to the query
    query_with_pdf_filter = f"{query} filetype:pdf"

    for attempt in range(retries):
        try:
            logger.info(f"Attempting Bing search (Attempt {attempt + 1}) for query: {query_with_pdf_filter}")

            # Perform the search with the query filter and PDF filetype
            response = session.get(bing_api_url, params={"q": query_with_pdf_filter}, timeout=10)

            # Check if request was successful
            if response.status_code == 200:
                results = response.json().get('webPages', {}).get('value', [])
                logger.info(f"Successfully retrieved {len(results)} results.")
                
                valid_pdf_links = []
                for result in results:
                    link = result.get('url', '')
                    if link.endswith('.pdf'):
                        valid_pdf_links.append(link)
                    else:
                        # make head request to check content type, include if content type valid type
                        try:
                            head_response = session.head(link, timeout=5)
                            if head_response.headers.get('Content-Type') == 'application/pdf':
                                valid_pdf_links.append(link)
                        except requests.RequestException as e:
                            logger.warning(f"Failed to verify content-type for {link}: {e}")
                            
                logger.info(f"Successfully retrieved {len(valid_pdf_links)} valid PDF links.")
                return valid_pdf_links  # Return if successful
                        
            elif response.status_code == 429:  # Rate limit error code
                logger.error(f"Rate limit hit during Bing search (Attempt {attempt + 1}).")
            else:
                logger.error(f"Error during Bing search (Attempt {attempt + 1}): {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Request error during Bing search (Attempt {attempt + 1}): {e}")

        # Implement exponential backoff with a cap
        if attempt < retries - 1:  # Don't delay after the last attempt
            delay = min(delay * 2, max_delay)  # Increase the delay but cap it
            logger.info(f"Waiting {delay} seconds before retrying...")
            time.sleep(delay)

    logger.error("Failed to retrieve data after multiple attempts.")
    return None
