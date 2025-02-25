from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
import time
import os
import logging
import traceback
import shutil
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# We can use the same config as the example since the parameters for the tool are the same
from .asce_config import ASCEToolConfig


@dataclass
class ASCEReportConfig:
    """Configuration for ASCE Report download functionality"""
    download_directory: str  # Temporary directory for downloads
    wait_time: int = 60  # Time to wait for download to complete


class ASCEReportScraper:
    """Handles web scraping and downloading of ASCE Hazard Tool reports"""
    
    def __init__(self, config: ASCEReportConfig = None):
        """Initialize the scraper with optional config"""
        self.driver = None
        self.temp_dir = None
        self.config = config or ASCEReportConfig(
            download_directory=os.path.join(os.getcwd(), "temp_downloads"),
            wait_time=90
        )
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Sets up logging for the scraper"""
        logger = logging.getLogger('asce_report_scraper')
        logger.setLevel(logging.INFO)
        
        # Avoid adding duplicate handlers if logger already exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger

    def initialize_driver(self) -> bool:
        """Initialize and configure the Chrome WebDriver"""
        try:
            import tempfile
            import shutil
            
            # Create unique temp directory for gunicorn workers to use
            self.temp_dir = tempfile.mkdtemp()
            self.logger.info(f"Created temporary directory: {self.temp_dir}")
            
            options = webdriver.ChromeOptions()
            options.page_load_strategy = 'normal'
            
            # Configure download behavior
            prefs = {
                "download.default_directory": self.temp_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": False
            }
            options.add_experimental_option("prefs", prefs)
            
            options.add_argument('--no-sandbox')
            #options.add_argument('--headless')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--user-data-dir={self.temp_dir}')
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.logger.info("WebDriver initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize driver: {str(e)}")
            if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            return False

    def initial_page_load(self, timeout: int = 40) -> Tuple[bool, Dict[str, bool]]:
        """
        Optimized initial page load detection that checks essential elements.
        
        Args:
            timeout: Maximum wait time in seconds (default 40s)
            
        Returns:
            bool: True if all checks pass, False otherwise
            dict: Status of individual checks
        """
        try:
            start_time = time.time()
            self.logger.info("Starting initial page load check...")
            
            checks_status = {
                'document_ready': False,
                'jquery_ready': False,
                'search_input_visible': False,
                'search_button_visible': False
            }

            # 1. Document Ready State Check
            try:
                WebDriverWait(self.driver, timeout).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                checks_status['document_ready'] = True
                self.logger.info("Document ready state complete")
            except TimeoutException:
                self.logger.error("Error: Document ready state timeout")
                return False, checks_status

            # 2. jQuery Ready Check
            try:
                jquery_check = """
                    return (typeof jQuery !== 'undefined' && 
                            jQuery.active === 0 && 
                            typeof jQuery.ajax === 'function')
                """
                WebDriverWait(self.driver, timeout).until(
                    lambda d: d.execute_script(jquery_check)
                )
                checks_status['jquery_ready'] = True
                self.logger.info("jQuery state ready")
            except TimeoutException:
                self.logger.warning("Warning: jQuery not ready, but continuing...")
                # Don't return False as jQuery might not be critical

            # 3. Search Input Visibility Check
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#geocoder_input"))
                )
                checks_status['search_input_visible'] = True
                self.logger.info("Search input field located")
            except TimeoutException:
                self.logger.error("Error: Search input not found")
                return False, checks_status

            # 4. Search Button Visibility Check
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#locate-address"))
                )
                checks_status['search_button_visible'] = True
                self.logger.info("Search button located")
            except TimeoutException:
                self.logger.error("Error: Search button not found")
                return False, checks_status

            # Final delay to ensure stable page state
            time.sleep(5)
            
            # Calculate execution time
            elapsed_time = time.time() - start_time
            self.logger.info(f"Initial page load completed in {elapsed_time:.2f} seconds")
            
            # Success requires all critical checks to pass
            success = all([
                checks_status['document_ready'],
                checks_status['search_input_visible'],
                checks_status['search_button_visible']
            ])
            
            return success, checks_status

        except Exception as e:
            self.logger.error(f"Critical error during initial page load: {str(e)}")
            traceback.print_exc()
            return False, checks_status

    def wait_for_element(self, selector: str, timeout: int = 30) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Waits for an element to be present in the DOM.
        
        Args:
            selector: CSS selector string
            timeout: Maximum wait time in seconds
            
        Returns:
            WebElement if found, None if not found
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            self.logger.info(f"Element found: {selector}")
            return element
        except TimeoutException:
            self.logger.error(f"Error: Element not found within {timeout} seconds: {selector}")
            return None
        except Exception as e:
            self.logger.error(f"Error waiting for element {selector}: {str(e)}")
            return None

    def click_element(self, element: webdriver.remote.webelement.WebElement) -> bool:
        """
        Attempts to click an element with JavaScript fallback.
        
        Args:
            element: WebElement to click
            
        Returns:
            bool: True if click successful, False otherwise
        """
        if element is None:
            self.logger.error("Error: Cannot click None element")
            return False
            
        try:
            element.click()
            self.logger.info("Element clicked successfully")
            return True
        except ElementClickInterceptedException:
            try:
                self.driver.execute_script("arguments[0].click();", element)
                self.logger.info("Element clicked successfully via JavaScript")
                return True
            except Exception as e:
                self.logger.error(f"Error clicking element via JavaScript: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error clicking element: {str(e)}")
            return False

    def enter_text(self, element: webdriver.remote.webelement.WebElement, text: str) -> bool:
        """
        Enters text into an input element.
        
        Args:
            element: WebElement to enter text into
            text: String to enter
            
        Returns:
            bool: True if text entry successful, False otherwise
        """
        if element is None:
            self.logger.error("Error: Cannot enter text into None element")
            return False
            
        try:
            element.clear()
            element.send_keys(text)
            self.logger.info(f"Text entered successfully: {text}")
            return True
        except Exception as e:
            self.logger.error(f"Error entering text: {str(e)}")
            return False

    def select_dropdown_option(self, dropdown_element: webdriver.remote.webelement.WebElement, option_value: str, timeout: int = 30) -> bool:
        """
        Selects the specified option from a dropdown element.
    
        Args:
            dropdown_element: WebElement representing the dropdown
            option_value: The value attribute of the option to select
            timeout: Maximum wait time in seconds
        
        Returns:
            bool: True if selection was successful, False otherwise
        """
        try:
            # Create Select object
            dropdown = Select(dropdown_element)
        
            # Wait for options to be present (important for dependent dropdowns)
            WebDriverWait(self.driver, timeout).until(
                lambda _: len(dropdown.options) > 1
            )
        
            # Select the option
            dropdown.select_by_value(option_value)
            self.logger.info(f"Selected option '{option_value}' from dropdown")
            return True
        
        except Exception as e:
            self.logger.error(f"Error selecting option from dropdown: {str(e)}")
            return False

    def wait_for_download(self, timeout: int = 90) -> Optional[str]:
        """
        Waits for a file download to complete within specified timeout.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            Path to downloaded file if successful, None otherwise
        """
        start_time = time.time()
        self.logger.info(f"Waiting for download to complete (timeout: {timeout}s)...")
        
        while (time.time() - start_time) < timeout:
            # Check if any files have been downloaded
            files = os.listdir(self.temp_dir)
            pdf_files = [f for f in files if f.endswith('.pdf')]
            
            # Check for PDF files
            if pdf_files:
                # Check if any file has a size greater than 0 and doesn't end with .crdownload
                for pdf_file in pdf_files:
                    file_path = os.path.join(self.temp_dir, pdf_file)
                    if os.path.getsize(file_path) > 0:
                        self.logger.info(f"Download completed: {file_path}")
                        return file_path
            
            # Sleep briefly before checking again
            time.sleep(1)
        
        self.logger.error(f"Download timeout after {timeout}s")
        return None

    def save_report(self, download_path: str, destination_path: str) -> bool:
        """
        Saves the downloaded report to the specified destination path.
        
        Args:
            download_path: Path to the downloaded file
            destination_path: Full path where the file should be saved
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            # Log the full paths for debugging
            self.logger.info(f"Download path: {download_path}")
            self.logger.info(f"Destination path: {destination_path}")
            
            # Check if destination directory exists
            dest_dir = os.path.dirname(destination_path)
            self.logger.info(f"Checking if directory exists: {dest_dir}")
        
            if not os.path.exists(dest_dir):
                self.logger.error(f"Directory does not exist: {dest_dir}")
                return False
            
            # Copy the file to destination
            shutil.copy2(download_path, destination_path)
            self.logger.info(f"Report saved to: {destination_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving report: {str(e)}")
            return False
        
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.logger.info("WebDriver closed")
            
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                self.logger.info(f"Temporary directory removed: {self.temp_dir}")
                self.temp_dir = None
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")

    def run_report_download(self, address: str, 
                           standard_version: str, 
                           risk_category: str, 
                           soil_class: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Main method to execute the web scraping and report download process.
        
        Args:
            address: Project address to search
            standard_version: ASCE Standard Version (e.g. "7-16")
            risk_category: Risk Category (e.g. "2")
            soil_class: Site Soil Class (e.g. "5")
            
        Returns:
            Tuple containing:
            - Success status (bool)
            - Error message if any (Optional[str])
            - Path to downloaded file if successful (Optional[str])
        """
        # Validate inputs using ASCEToolConfig
        if not ASCEToolConfig.validate_selections(standard_version, risk_category, soil_class):
            error_msg = "Invalid input selections provided"
            self.logger.error(error_msg)
            return False, error_msg, None
        
        try:
            # Initialize driver if not already initialized
            if not self.driver:
                if not self.initialize_driver():
                    return False, "Failed to initialize browser", None
            
            # Open the webpage
            self.logger.info("Navigating to the ASCE Hazard Tool...")
            self.driver.get("https://ascehazardtool.org/")
            
            # Initial page load check
            success, status = self.initial_page_load()
            if not success:
                failed_checks = [k for k, v in status.items() if not v]
                return False, f"Failed initial page load checks: {failed_checks}", None
            
            time.sleep(12)
            
            # Close cookie popup
            self.logger.info("Closing cookie popup...")
            cookie_element = self.wait_for_element(".cc-btn.cc-dismiss")
            if cookie_element:
                if not self.click_element(cookie_element):
                    self.logger.warning("Failed to close cookie popup")
                    
            time.sleep(1)
            
            # Close ASCE hazard popup
            self.logger.info("Closing ASCE hazard tool popup...")
            hazard_element = self.wait_for_element("#welcomePopup > div.popup-header.blue.darken-3.welcome-header > span.details-popup-close-icon")
            if hazard_element:
                if not self.click_element(hazard_element):
                    self.logger.warning("Failed to close ASCE hazard popup")
                    
            time.sleep(2)
            
            # Enter address and search
            self.logger.info(f"Entering address: {address}")
            input_element = self.wait_for_element("#geocoder_input")
            if not input_element or not self.enter_text(input_element, address):
                return False, "Failed to enter address", None
            
            time.sleep(3)
            
            # Click search button
            self.logger.info("Clicking search button...")
            search_element = self.wait_for_element("#locate-address")
            if not search_element or not self.click_element(search_element):
                return False, "Failed to click search button", None
                
            time.sleep(5)
            
            # Select dropdowns
            dropdown_configs = [
                ("#standards-selector", standard_version),
                ("#risk-level-selector", risk_category),
                ("#site-soil-class-selector", soil_class)
            ]
        
            for selector, value in dropdown_configs:
                dropdown_element = self.wait_for_element(selector)
                if not dropdown_element or not self.select_dropdown_option(dropdown_element, value):
                    return False, f"Failed to select option {value} for {selector}", None
                time.sleep(2)
            
            time.sleep(3)
            
            # Select load types
            base_selector = "#criteria .flex.flex-row.flex-wrap.padding--small"
            load_types = ["Wind", "Seismic", "Ice", "Snow"]
        
            for i, load_type in enumerate(load_types, 1):
                selector = f"{base_selector} p:nth-child({i}) label"
                load_element = self.wait_for_element(selector)
                if not load_element or not self.click_element(load_element):
                    self.logger.warning(f"Failed to select {load_type} Load")
                time.sleep(2)
            
            time.sleep(2)
            
            # Click View Results
            self.logger.info("Clicking View Results button...")
            results_element = self.wait_for_element("#resultsButton > a")
            if not results_element or not self.click_element(results_element):
                return False, "Failed to click results button", None
            
            # Wait for results to load
            time.sleep(30)
            
            # Click Download Full Report button
            self.logger.info("Clicking Download Full Report button...")
            report_selector = "#report > div.full-report-container.padding--small.white > a:nth-child(2)"
            report_element = self.wait_for_element(report_selector)
            if not report_element or not self.click_element(report_element):
                return False, "Failed to click Download Full Report button", None
            
            time.sleep(30)
            
            # Wait for download to complete
            download_path = self.wait_for_download(self.config.wait_time)
            if not download_path:
                return False, "Download failed or timed out", None
            
            time.sleep(10)
            
            # Close final popup if it appears
            self.logger.info("Closing final popup if present...")
            final_popup = "#detailsPopup > div.fill_wide.padding__long.white.popup-ok-button > a"
            final_element = self.wait_for_element(final_popup)
            if final_element:
                if not self.click_element(final_element):
                    self.logger.warning("Failed to close final popup")
            
            # Create a copy of the download path because we'll be deleting the original
            temp_copy = None
            try:
                # Create a temporary file in a system temp directory that won't be deleted
                import tempfile
                temp_fd, temp_copy = tempfile.mkstemp(suffix='.pdf')
                os.close(temp_fd)  # Close the file descriptor
            
                # Copy the file to our safe temporary location
                shutil.copy2(download_path, temp_copy)
                self.logger.info(f"Created temporary copy at: {temp_copy}")
            except Exception as e:
                self.logger.error(f"Error creating temporary copy: {str(e)}")
                return False, f"Error creating temporary copy: {str(e)}", None
            
            # Return the path to the temporary copy
            return True, None, temp_copy
            
        except Exception as e:
            error_msg = f"Error during report download process: {str(e)}"
            self.logger.error(error_msg)
            traceback.print_exc()
            return False, error_msg, None
        
        finally:
            self.cleanup()