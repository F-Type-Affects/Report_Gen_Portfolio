import logging
import time
import requests
import random
import pandas as pd
import os
import platform
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app.core.config import get_config

config = get_config()

logger = logging.getLogger(__name__)

def get_chromedriver_path():
    """
    Get the path to ChromeDriver based on the operating system.
    
    Returns:
        str: Path to ChromeDriver executable or None if not found.
    """
    # Determine the ChromeDriver filename based on OS
    system = platform.system()
    if system == "Windows":
        driver_name = "chromedriver.exe"
    else:
        driver_name = "chromedriver"
    
    # Get the path to the drivers directory
    current_file = os.path.abspath(__file__)
    back_end_dir = os.path.dirname(current_file)
    utils_dir = os.path.join(back_end_dir, "utils", "drivers")
    driver_path = os.path.join(utils_dir, driver_name)
    
    # Check if the driver exists
    if os.path.exists(driver_path):
        logger.info(f"Found ChromeDriver at: {driver_path}")
        return driver_path
    else:
        logger.warning(f"ChromeDriver not found at: {driver_path}")
        logger.warning(f"Please place {driver_name} in {utils_dir}")
        return None

# Initialize web driver for Selenium to search AHJ registry
def init_driver():
    """
    Initializes a headless Chrome WebDriver with custom options.
    Returns:
        WebDriver: Configured Selenium WebDriver instance.
    """
    logger.info("Initializing Selenium WebDriver.")
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    # Remove --start-fullscreen and add window size
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Add these options from base_scraper.py
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument('--log-level=3')
    
    # Get ChromeDriver path
    chromedriver_path = get_chromedriver_path()
    
    if chromedriver_path:
        # Use the ChromeDriver from our drivers directory
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome driver initialized using project ChromeDriver")
    else:
        # Fallback to system ChromeDriver
        driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome driver initialized using system ChromeDriver")
    
    return driver

# Function to search AHJ registry
def search_ahj_registry(address):
    logger.info(f"Starting AHJ registry search for address: {address}")
    email = config.LOGIN
    pw = config.PW
    driver = init_driver()
    
    try:
        driver.get('https://ahjregistry.myorangebutton.com/#/ahj-search')
        logger.debug("Navigated to AHJ registry website.")

        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login-btn"]')))
        driver.find_element(By.XPATH, '//*[@id="login-btn"]').click()
        logger.debug("Clicked login button.")

        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[1]/input')))
        driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[1]/input').send_keys(email)
        driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/div[2]/input').send_keys(pw)
        driver.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/div/div/div/div/div/form/div/button').click()
        logger.info("Logged into AHJ registry.")

        WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button')))
        driver.find_element(By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button').click()
        logger.debug("Closed login modal.")

        WebDriverWait(driver, 20).until_not(EC.presence_of_element_located((By.XPATH, '//*[@id="login-modal___BV_modal_header_"]/button')))
        search_box = driver.find_element(By.XPATH, '//*[@id="search-bar-input"]')
        search_box.send_keys(address)
        search_box.send_keys(Keys.RETURN)
        logger.info("Entered address and initiated search.")

        WebDriverWait(driver, 20).until_not(EC.text_to_be_present_in_element((By.XPATH, '/html/body/div/div/div[3]/div[2]/div/table/tbody'), 'Loading...'))
        table = driver.find_element(By.XPATH, '/html/body/div/div/div[3]/div[2]/div/table')
        rows = table.find_elements(By.TAG_NAME, 'tr')

        table_data = []
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, 'td')
            if len(cols) > 0:
                table_data.append([col.text for col in cols])
        logger.info(f"Retrieved {len(table_data)} rows from AHJ registry.")

        # Convert table data to a DataFrame and return as JSON serializable
        df = pd.DataFrame(table_data, columns=['AHJ Code', 'AHJ Name', 'County', 'Building Code', 'Electric Code', 'Fire Code', 'Residential Code', 'Wind Code', 'More Info'])
        return df.to_dict(orient='records')
    except Exception as e:
        logger.error(f"Error during AHJ registry search: {e}")
        return []
    finally:
        driver.quit()

# Function to perform Bing search with exponential backoff and PDF filter and regular websites
def perform_bing_search(query, retries=5):

    logger.info(f"Starting Bing search for query: {query}")
    bing_api_url = f"{config.BING_ENDPOINT}v7.0/search"  # Bing Search API endpoint
    api_key = config.BING_KEY  # Your Bing API key from Azure
    delay = 1  # Start with a 1-second delay
    max_delay = 60  # Cap delay to avoid long waits

    # Create a custom session for making API calls
    session = requests.Session()
    session.headers.update({
        "Ocp-Apim-Subscription-Key": api_key  # Bing API key
    })

    # Queries for both PDFs and websites
    query_pdf = f"{query} filetype:pdf"
    query_web = f"{query}"

    pdf_results = []
    web_results = []

    # Helper function to perform the search
    def perform_search(query_with_filter):
        for attempt in range(retries):
            try:
                logger.info(f"Attempting Bing search (Attempt {attempt + 1}) for query: {query_with_filter}")

                # Perform the search with the query filter
                response = session.get(bing_api_url, params={"q": query_with_filter}, timeout=10)

                # Check if request was successful
                if response.status_code == 200:
                    return response.json().get('webPages', {}).get('value', [])
                elif response.status_code == 429:  # Rate limit error code
                    logger.error(f"Rate limit hit during Bing search (Attempt {attempt + 1}).")
                else:
                    logger.error(f"Error during Bing search (Attempt {attempt + 1}): {response.status_code} - {response.text}")
            except requests.RequestException as e:
                logger.error(f"Request error during Bing search (Attempt {attempt + 1}): {e}")

            # Implement exponential backoff with a cap
            if attempt < retries - 1:  # Don't delay after the last attempt
                nonlocal delay
                delay = min(delay * 2, max_delay)  # Increase the delay but cap it
                logger.info(f"Waiting {delay} seconds before retrying...")
                time.sleep(delay)

        logger.error("Failed to retrieve data after multiple attempts.")
        return None

    # Perform search for PDFs
    pdf_results = perform_search(query_pdf)
    if pdf_results:
        pdf_links = []
        for result in pdf_results:
            link = result.get('url', '')
            if link.endswith('.pdf'):
                pdf_links.append(link)
            else:
                # Make head request to check content type, include if content type valid type
                try:
                    head_response = session.head(link, timeout=5)
                    if head_response.headers.get('Content-Type') == 'application/pdf':
                        pdf_links.append(link)
                except requests.RequestException as e:
                    logger.warning(f"Failed to verify content-type for {link}: {e}")
        logger.info(f"Successfully retrieved {len(pdf_links)} valid PDF links.")
    else:
        pdf_links = []

    # Perform search for general websites
    web_results = perform_search(query_web)
    if web_results:
        web_links = [result.get('url', '') for result in web_results[:8]]  # Limit to top 8 web links
        logger.info(f"Successfully retrieved {len(web_links)} valid web links.")
    else:
        web_links = []

    return pdf_links, web_links