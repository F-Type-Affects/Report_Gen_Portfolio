from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
import time
import logging
from dataclasses import dataclass
from .asce_config import ASCEToolConfig
from .models import ASCESummaryData
from typing import Dict, Tuple, Optional
import os
import openpyxl


class ASCEScraper:
    """Handles web scraping of ASCE Hazard Tool data"""
    
    def __init__(self):
        """Initialize the scraper"""
        self.driver = None
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Sets up logging for the scraper"""
        logger = logging.getLogger('asce_scraper')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

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

    def initialize_driver(self) -> bool:
        """Initialize and configure the Chrome WebDriver"""
        try:
            import tempfile
            import shutil
            
            # create unique temp directory for gunicorn workers to use
            self.temp_dir = tempfile.mkdtemp()
            
            
            options = webdriver.ChromeOptions()
            options.page_load_strategy = 'normal'
            options.add_argument('--no-sandbox')
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--user-data-dir={self.temp_dir}')
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            return True
        except Exception as e:
            if hasattr(self, 'temp_dir'):
                shutil.rmtree(self.temp_dir,ignore_errors=True)
            self.logger.error(f"Failed to initialize driver: {str(e)}")
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

    def extract_table_data(self, timeout: int = 30) -> Dict:
        """
        Extracts data from the ASCE summary table handling all nested elements.
    
        Args:
            timeout: Maximum wait time in seconds
        
        Returns:
            Dictionary containing the table data
        """
        table_data = {}
        try:
            # Use reliable XPath that combines ID and class
            table_selector = "#summaryPopup > div.popup-body.padding.welcome-body"
        
            # Wait for table to be present
            table = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            self.logger.info("Summary table found")
        
            current_section = None
            rows = table.find_elements(By.TAG_NAME, "tr")
        
            for row in rows:
                if "summary-header-row" in row.get_attribute("class"):
                    current_section = row.find_element(By.TAG_NAME, "td").text.strip()
                    table_data[current_section] = []
                
                elif "summary-item-row" in row.get_attribute("class"):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) == 2 and current_section:
                        # Get parameter and value including any sub/superscripts
                        param = cells[0].get_attribute('textContent').strip()
                        value = cells[1].get_attribute('textContent').strip()
                    
                        table_data[current_section].append({
                            'parameter': param,
                            'value': value
                        })

        except TimeoutException:
            self.logger.error("Timeout waiting for summary table")
            raise
        except Exception as e:
            self.logger.error(f"Error extracting table data: {str(e)}")
            raise

        return table_data

    def save_summary_to_excel(self, summary_data: Dict) -> Optional[str]:
        """
        Saves the extracted summary data to Excel.
    
        Args:
            summary_data: Dictionary containing the table data
        
        Returns:
            str: Path to saved file if successful, None if failed
        """
        try:
            os.makedirs(self.config.save_directory, exist_ok=True)
        
            workbook = openpyxl.Workbook()
            sheet = workbook.active
        
            # Add headers
            headers = ["Section", "Parameter", "Value"]
            for col, header in enumerate(headers, 1):
                cell = sheet.cell(row=1, column=col)
                cell.value = header
                cell.font = openpyxl.styles.Font(bold=True)
        
            current_row = 2
        
            # Write data section by section
            for section, items in summary_data.items():
                # Add section header
                sheet.cell(row=current_row, column=1, value=section)
                current_row += 1
            
                # Add section items
                for item in items:
                    sheet.cell(row=current_row, column=2, value=item['parameter'])
                    sheet.cell(row=current_row, column=3, value=item['value'])
                    current_row += 1
            
                # Add blank row between sections
                current_row += 1
        
            # Save the workbook
            file_path = os.path.join(self.config.save_directory, "summary_data.xlsx")
            workbook.save(file_path)
        
            self.logger.info(f"Data saved to: {file_path}")
            return file_path
        
        except Exception as e:
            self.logger.error(f"Error saving to Excel: {str(e)}")
            return None
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
            
            if hasattr(self, 'temp_dir'):
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
                

    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                
            if hasattr(self, 'temp_dir'):
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
           self.logger.error(f"Error during cleanup: {str(e)}") 


    def run_scraping_process(self, address: str, standard_version: str, risk_category: str, soil_class: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Main method to execute the web scraping process.
    
        Args:
            address: Project address to search
            standard_version: ASCE Standard Version (e.g., "7-16")
            risk_category: Risk Category (e.g., "2")
            soil_class: Site Soil Class (e.g., "5")
        
        Returns:
            Tuple containing:
            - Success status (bool)
            - Error message if any (Optional[str])
            - Summary data if successful (Optional[Dict])
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
            self.driver.get("https://ascehazardtool.org/")
        
            # Initial page load check
            success, status = self.initial_page_load()
            if not success:
                failed_checks = [k for k, v in status.items() if not v]
                return False, f"Failed initial page load checks: {failed_checks}", None
        
            time.sleep(12)
        
            # Close cookie popup
            cookie_element = self.wait_for_element(".cc-btn.cc-dismiss")
            if cookie_element:
                if not self.click_element(cookie_element):
                    self.logger.warning("Failed to close cookie popup")
        
            time.sleep(3)
        
            # Close ASCE hazard popup
            hazard_element = self.wait_for_element("#welcomePopup > div.popup-header.blue.darken-3.welcome-header > span.details-popup-close-icon")
            if hazard_element:
                if not self.click_element(hazard_element):
                    self.logger.warning("Failed to close ASCE hazard popup")
        
            time.sleep(2)
        
            # Enter address
            input_element = self.wait_for_element("#geocoder_input")
            if not input_element or not self.enter_text(input_element, address):
                return False, "Failed to enter address", None
        
            time.sleep(3)
        
            # Click search
            search_element = self.wait_for_element("#locate-address")
            if not search_element or not self.click_element(search_element):
                return False, "Failed to click search button", None

            time.sleep(10)
        
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

            time.sleep(3)
        
            # Click View Results
            results_element = self.wait_for_element("#resultsButton > a")
            if not results_element or not self.click_element(results_element):
                return False, "Failed to click results button", None
        
            time.sleep(30)
        
            # Click Summary Button
            summary_element = self.wait_for_element("#report > div.full-report-container.padding--small.white > a:nth-child(3)")
            if not summary_element or not self.click_element(summary_element):
                return False, "Failed to click summary button", None
        
            time.sleep(5)
        
            # Extract table data
            summary_data_dict = self.extract_table_data()
            if not summary_data_dict:
                return False, "Failed to extract table data", None
            
            time.sleep(2)
            
            # Convert dictionary to ASCESummaryData
            summary_data = ASCESummaryData.from_dict(summary_data_dict)
            
            # Close summary table
            table_close_element = self.wait_for_element("#summaryPopup > div.popup-header.blue.darken-3.welcome-header > span.details-popup-close-icon")
            if table_close_element:
                if not self.click_element(table_close_element):
                    self.logger.warning("Failed to close summary table")
        
            time.sleep(1)
            
            return True, None, summary_data

        except Exception as e:
            error_msg = f"Error during scraping process: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg, None
        
        finally:
            self.cleanup()