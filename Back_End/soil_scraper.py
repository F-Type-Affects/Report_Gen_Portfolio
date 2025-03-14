from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import logging
import os
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List
import shutil
import traceback

@dataclass
class SoilScraperConfig:
    """Configuration for Web Soil Survey scraper download functionality"""
    download_directory: str  # Temporary directory for downloads
    wait_time: int = 90  # Time to wait for download to complete

class WebSoilSurveyScraper:
    """Web scraper for the Web Soil Survey website"""
    
    def __init__(self, config: SoilScraperConfig = None):
        """Initialize the scraper with optional config"""
        self.driver = None
        self.temp_dir = None
        self.config = config or SoilScraperConfig(
            download_directory=os.path.join(os.getcwd(), "temp_downloads"),
            wait_time=90
        )
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Sets up logging for the scraper"""
        logger = logging.getLogger('web_soil_survey_scraper')
        logger.setLevel(logging.INFO)
        
        # Create handler if none exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
    
    def initialize_driver(self, download_path=None) -> bool:
        """Initialize and configure the Chrome WebDriver"""
        try:
            import tempfile
        
            # Use provided download path or create a temporary directory
            if download_path:
                self.temp_dir = download_path
            else:
                self.temp_dir = tempfile.mkdtemp()
        
            self.logger.info(f"Using download directory: {self.temp_dir}")
        
            # Ensure the download directory exists
            os.makedirs(self.temp_dir, exist_ok=True)
        
            options = webdriver.ChromeOptions()
            options.page_load_strategy = 'normal'
        
            # Configure download behavior
            prefs = {
                "download.default_directory": self.temp_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "plugins.always_open_pdf_externally": True,
                "download.open_pdf_in_system_reader": False,
                "browser.helperApps.neverAsk.saveToDisk": "application/pdf",
                "safebrowsing.enabled": False
            }
        
            options.add_experimental_option("prefs", prefs)
        
            # Add arguments for better performance and stability
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
        
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
        
            # Use CDP to set download behavior
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": self.temp_dir
            })
        
            self.logger.info("WebDriver initialized successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to initialize driver: {str(e)}")
            return False
    
    def wait_for_element(self, selector: str, timeout: int = 30) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Waits for an element to be present and visible in the DOM.
        
        Args:
            selector: CSS selector string
            timeout: Maximum wait time in seconds
            
        Returns:
            WebElement if found, None if not found
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
            )
            self.logger.info(f"Element found: {selector}")
            return element
        except TimeoutException:
            self.logger.error(f"Error: Element not found within {timeout} seconds: {selector}")
            return None
        except Exception as e:
            self.logger.error(f"Error waiting for element {selector}: {str(e)}")
            return None
    
    def wait_for_element_clickable(self, selector: str, timeout: int = 30) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Waits for an element to be clickable in the DOM.
        
        Args:
            selector: CSS selector string
            timeout: Maximum wait time in seconds
            
        Returns:
            WebElement if clickable, None if not clickable
        """
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            self.logger.info(f"Element clickable: {selector}")
            return element
        except TimeoutException:
            self.logger.error(f"Error: Element not clickable within {timeout} seconds: {selector}")
            return None
        except Exception as e:
            self.logger.error(f"Error waiting for element to be clickable {selector}: {str(e)}")
            return None
    
    def click_element(self, element: webdriver.remote.webelement.WebElement, description: str = "element") -> bool:
        """
        Attempts to click an element with JavaScript fallback.
        
        Args:
            element: WebElement to click
            description: Description of the element for logging
            
        Returns:
            bool: True if click successful, False otherwise
        """
        if element is None:
            self.logger.error(f"Error: Cannot click None {description}")
            return False
            
        try:
            # Try regular click first
            element.click()
            self.logger.info(f"{description} clicked successfully")
            return True
        except ElementClickInterceptedException:
            # Fallback to JavaScript click if regular click is intercepted
            try:
                self.driver.execute_script("arguments[0].click();", element)
                self.logger.info(f"{description} clicked successfully via JavaScript")
                return True
            except Exception as e:
                self.logger.error(f"Error clicking {description} via JavaScript: {str(e)}")
                return False
        except Exception as e:
            self.logger.error(f"Error clicking {description}: {str(e)}")
            
            # Try scrolling to element and clicking again
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(1)  # Give time for scroll to complete
                element.click()
                self.logger.info(f"{description} clicked successfully after scrolling")
                return True
            except Exception as scroll_error:
                self.logger.error(f"Error clicking {description} after scrolling: {str(scroll_error)}")
                return False
    
    def enter_text(self, element: webdriver.remote.webelement.WebElement, text: str, description: str = "field") -> bool:
        """
        Enters text into an input element.
        
        Args:
            element: WebElement to enter text into
            text: String to enter
            description: Description of the field for logging
            
        Returns:
            bool: True if text entry successful, False otherwise
        """
        if element is None:
            self.logger.error(f"Error: Cannot enter text into None {description}")
            return False
            
        try:
            # Scroll element into view first
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)  # Give time for scroll to complete
            
            # Clear the field and enter text
            element.clear()
            element.send_keys(text)
            self.logger.info(f"Text entered successfully into {description}: {text}")
            return True
        except Exception as e:
            self.logger.error(f"Error entering text into {description}: {str(e)}")
            return False
    
    def switch_to_new_tab(self, wait_time: int = 5) -> bool:
        """
        Switches to the most recently opened tab.
        
        Args:
            wait_time: Time to wait for the new tab to open
            
        Returns:
            bool: True if switch successful, False otherwise
        """
        try:
            # Wait for new tab to open
            time.sleep(wait_time)
            
            # Get all window handles and switch to the last one (most recently opened)
            tabs = self.driver.window_handles
            
            if len(tabs) < 2:
                self.logger.error("No new tab found to switch to")
                return False
                
            # Switch to the new tab
            self.driver.switch_to.window(tabs[-1])
            self.logger.info(f"Switched to new tab with URL: {self.driver.current_url}")
            return True
        except Exception as e:
            self.logger.error(f"Error switching to new tab: {str(e)}")
            return False
    
    def navigate_to_website(self, url: str) -> bool:
        """
        Navigates to the specified URL.
        
        Args:
            url: Website URL to navigate to
            
        Returns:
            bool: True if navigation successful, False otherwise
        """
        try:
            self.driver.get(url)
            self.logger.info(f"Navigated to {url}")
            
            # Wait for page to load completely
            WebDriverWait(self.driver, 30).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            
            time.sleep(5)
            
            self.logger.info("Page loaded completely")
            
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to {url}: {str(e)}")
            return False
    
    def find_address_input_field(self) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Finds the address input field.
    
        Returns:
            WebElement if found, None otherwise
        """
        self.logger.info("Looking for address input field...")
        address_field = self.wait_for_element("textarea[name='address']")
    
        if address_field:
            self.logger.info("Address field found")
            return address_field
        else:
            self.logger.error("Address field not found")
            return None

    def find_view_button(self) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Finds the View button.
    
        Returns:
            WebElement if found, None otherwise
        """
        self.logger.info("Looking for View button...")
        view_button = self.wait_for_element_clickable("#navigatebyaddressformid > div.controlbar.lastcontrolbar > button")
    
        if view_button:
            self.logger.info("View button found")
            return view_button
        else:
            self.logger.error("View button not found")
            return None
    
    def select_aoi_by_rectangle(self) -> bool:
        """
        Selects an Area of Interest (AOI) by dragging a small test rectangle
        starting at the map's absolute position.
    
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Wait for the map to load completely
            self.logger.info("Waiting for map to load completely...")
            time.sleep(5)
        
            # 1. Click the AOI Rectangle button
            aoi_button = self.wait_for_element_clickable("#aoi_rectangle_up")
            if not aoi_button:
                self.logger.error("AOI Rectangle button not found")
                return False
        
            if not self.click_element(aoi_button, "AOI Rectangle button"):
                return False
        
            self.logger.info("AOI Rectangle button clicked successfully")
            time.sleep(2)  # Wait for the tool to activate
        
            # 2. Use the known absolute coordinates of the map (420, 220)
            start_x = 420
            start_y = 220
        
            # 3. Create a small 100x100 test rectangle
            rectangle_width = 1500
            rectangle_height = 720
        
            self.logger.info(f"Drawing test rectangle from ({start_x},{start_y}) with size 1500x720")
        
            # 4. Execute the drag operation using absolute coordinates
            actions = ActionChains(self.driver)
        
            # Reset mouse position (move to 0,0)
            actions.move_by_offset(0, 0)
            actions.perform()
        
            # Create new action chain
            actions = ActionChains(self.driver)
        
            # Move to the start point and draw rectangle
            actions.move_by_offset(start_x, start_y)
            actions.click_and_hold()
            actions.move_by_offset(rectangle_width, rectangle_height)
            actions.release()
            actions.perform()
        
            self.logger.info("Test rectangle drag operation completed")
        
            # Wait for any processing after rectangle selection
            time.sleep(3)
        
            return True
        
        except Exception as e:
            self.logger.error(f"Error during AOI test rectangle selection: {str(e)}")
            return False
        
        
    def scroll_window(self, pixels: int = 300) -> bool:
        """
        Scrolls the window by the specified number of pixels.
    
        Args:
            pixels: Number of pixels to scroll (positive to scroll down, negative to scroll up)
    
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            direction = "down" if pixels > 0 else "up"
            self.logger.info(f"Scrolling window {direction} by {abs(pixels)} pixels...")
            self.driver.execute_script(f"window.scrollBy(0, {pixels});")
            time.sleep(1)  # Short wait to allow the scroll to complete
            self.logger.info("Scroll completed")
            return True
        except Exception as e:
            self.logger.error(f"Error scrolling window: {str(e)}")
            return False
    
    def select_dropdown_option(self, selector: str, option_value: str, description: str = "dropdown") -> bool:
        """
        Selects an option from a dropdown element by its value.
    
        Args:
            selector: CSS selector for the dropdown element
            option_value: Value attribute of the option to select
            description: Description of the dropdown for logging
        
        Returns:
            bool: True if selection successful, False otherwise
        """
        try:
            self.logger.info(f"Attempting to select '{option_value}' from {description}...")
        
            # First, find the dropdown element
            dropdown_element = self.wait_for_element(selector)
            if not dropdown_element:
                self.logger.error(f"{description} not found")
                return False
        
            # Create a Select object
            from selenium.webdriver.support.ui import Select
            dropdown = Select(dropdown_element)
        
            # Select by value
            dropdown.select_by_value(option_value)
        
            self.logger.info(f"Successfully selected '{option_value}' from {description}")
            time.sleep(1)  # Short wait after selection
            return True
        
        except Exception as e:
            self.logger.error(f"Error selecting option from {description}: {str(e)}")
            return False
        
    def wait_for_download(self, timeout: int = 90) -> List[str]:
        """
        Waits for file downloads to complete within specified timeout.
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            List of paths to downloaded files if successful, empty list otherwise
        """
        start_time = time.time()
        self.logger.info(f"Waiting for downloads to complete (timeout: {timeout}s)...")
        
        # Keep track of found files
        found_files = []
        
        while (time.time() - start_time) < timeout:
            # Check if any files have been downloaded
            files = os.listdir(self.temp_dir)
            pdf_files = [f for f in files if f.endswith('.pdf')]
            
            # Check for PDF files
            for pdf_file in pdf_files:
                file_path = os.path.join(self.temp_dir, pdf_file)
                if os.path.getsize(file_path) > 0 and file_path not in found_files:
                    self.logger.info(f"Download completed: {file_path}")
                    found_files.append(file_path)
            
            # If we found two PDF files, we're done
            if len(found_files) >= 2:
                self.logger.info(f"Found {len(found_files)} PDF files, download complete")
                return found_files
                
            # Sleep briefly before checking again
            time.sleep(1)
        
        self.logger.error(f"Download timeout after {timeout}s")
        return found_files
        
    def run_soil_survey(self, address: str) -> Tuple[bool, Optional[str], Optional[List[str]]]:
        """
        Main method to execute the web scraping process.

        Args:
            address: Project address to search
    
        Returns:
            Tuple containing:
            - Success status (bool)
            - Error message if any (Optional[str])
            - List of paths to downloaded files if successful (Optional[List[str]])
        """
        try:
            # Initialize driver if not already initialized
            if not self.driver:
                if not self.initialize_driver(self.config.download_directory):
                    return False, "Failed to initialize browser", None
        
            # Run the workflow
            if not self.run_initial_workflow(address):
                return False, "Failed to complete soil survey workflow", None
        
            # Wait for downloads to complete
            downloaded_files = self.wait_for_download(self.config.wait_time)
        
            if not downloaded_files:
                return False, "No downloaded files found", None
        
            # Create temporary copies of the downloads
            temp_copies = []
            try:
                import tempfile
                for file_path in downloaded_files:
                    temp_fd, temp_copy = tempfile.mkstemp(suffix='.pdf')
                    os.close(temp_fd)  # Close the file descriptor
                    shutil.copy2(file_path, temp_copy)
                    temp_copies.append(temp_copy)
                    self.logger.info(f"Created temporary copy at: {temp_copy}")
            except Exception as e:
                self.logger.error(f"Error creating temporary copies: {str(e)}")
                return False, f"Error creating temporary copies: {str(e)}", None
        
            return True, None, temp_copies
    
        except Exception as e:
            error_msg = f"Error during soil survey process: {str(e)}"
            self.logger.error(error_msg)
            traceback.print_exc()
            return False, error_msg, None

    def run_initial_workflow(self, address: str) -> bool:
        """
        Runs the initial workflow for the Web Soil Survey website.
        
        Args:
            address: The address to search for
            
        Returns:
            bool: True if workflow completed successfully, False otherwise
        """
        try:
            # Initialize WebDriver if not already initialized
            if not self.driver:
                if not self.initialize_driver(self.config.download_directory):
                    return False
            
            # 1. Navigate to the homepage
            homepage_url = "https://websoilsurvey.nrcs.usda.gov/app/"
            if not self.navigate_to_website(homepage_url):
                return False
            
            time.sleep(3)
            
            # 2. Click the "Start WSS" button
            start_button = self.wait_for_element_clickable("#BEGIN_WSS")
            if not self.click_element(start_button, "Start WSS button"):
                return False
            
            time.sleep(3)
            
            # 3. Switch to the new tab
            if not self.switch_to_new_tab():
                return False
            
            # 4. Wait for the page to load in the new tab
            time.sleep(8)
            
            # 6. Click the address dropdown button
            self.logger.info("Clicking address button...")
            address_dropdown = self.wait_for_element_clickable("#Quick_Navigation_Address_header > span > span")
            if address_dropdown:
                if not self.click_element(address_dropdown, "Address dropdown button"):
                    self.logger.warning("Failed to click address dropdown, continuing anyway")
                time.sleep(3)  # Wait for expansion animation
            else:
                self.logger.warning("Address button not found, continuing anyway")
            
            # 7. Find and interact with the address field
            self.logger.info("Looking for address input field...")
            address_field = self.find_address_input_field()
            
            if not address_field:
                self.logger.error("Could not find address input field")
                return False
            
            if not self.enter_text(address_field, address, "Address input field"):
                return False
            
            time.sleep(3)
            
            # 8. Find and click the "View" button
            self.logger.info("Looking for View Address button...")
            view_button = self.find_view_button()
            
            if not view_button:
                self.logger.error("Could not find View Address button")
                return False
            
            if not self.click_element(view_button, "View address button"):
                return False
            
            # 9. Wait for the search to complete
            time.sleep(5)
            
            # 10. Select AOI by rectangle
            self.logger.info("Starting AOI rectangle selection...")
            if not self.select_aoi_by_rectangle():
                self.logger.error("AOI rectangle selection failed")
                return False
            
            time.sleep(10)
            
            # 11. Navigate to Soil Data Explorer tab
            self.logger.info("Attempting to click Soil Data Explorer tab...")
            soil_data_tab = self.wait_for_element_clickable("#Soil_Data_Explorer")
            if not soil_data_tab:
                self.logger.error("Soil Data Explorer tab not found or not clickable")
                return False
            
            if not self.click_element(soil_data_tab, "Soil Data Explorer tab"):
                return False
            
            time.sleep(10)
            
            # 12. Navigate to Soil Properties and Qualities tab
            self.logger.info("Attempting to click Soil Properties and Qualities tab...")
            properties_tab = self.wait_for_element_clickable("#Soil_Properties_and_Qualities")
            if not properties_tab:
                self.logger.error("Soil Properties and Qualities tab not found or not clickable")
                return False
            
            if not self.click_element(properties_tab, "Soil Properties and Qualities tab"):
                return False
            
            time.sleep(10)
            
            # 13. Click on Soil Physical properties tab
            self.logger.info("Clicking on Soil Physical Properties button. . .")
            physical_properties_button = self.wait_for_element("#Soil_Physical_Properties_unfold")
            if not physical_properties_button:
                self.logger.error("Physical Properties button not found")
                return False
            
            if not self.click_element(physical_properties_button, "Physical Properties Button"):
                return False
            
            time.sleep(10)
            
            # 14. click Linear Extensiability button
            self.logger.info("Clicking Linear Extensability Button. . .")
            linear_extens_button = self.wait_for_element_clickable("#Soil_Physical_Properties_Linear_Extensibility_header > span > span")
            if not linear_extens_button:
                self.logger.error("Linear Extensability button not found")
                return False
            
            if not self.click_element(linear_extens_button, "Linear Extensability Button"):
                return False
            
            time.sleep(8)
            
            # 15. Scroll the window
            self.logger.info("Scrolling down to see additional options. . .")
            if not self.scroll_window(500):
                self.logger.warning("Failed to scroll window")
                
            time.sleep(3)
            
            # 16. select dominant condition from drop down
            if not self.select_dropdown_option(
                selector="#Aggregation_Method_00000",
                option_value="Dominant Condition",
                description="Aggregation Method dropdown"
            ):
                self.logger.error("Failed to select the drop down option")
                return False
            
            time.sleep(5)
            
            # 17. Enter Top Depth value (2)
            self.logger.info("Entering 2 for top depth")
            top_depth_input = self.wait_for_element("input[name='Top_Depth']")
            if not top_depth_input:
                self.logger.error("Top Depth Input Field Not Found")
                return False

            if not self.enter_text(top_depth_input, "2", "Top Depth field"):
                return False

            # 18. Enter Bottom Depth value (60)
            self.logger.info("Entering 60 for bottom depth")
            bottom_depth_input = self.wait_for_element("input[name='Bottom_Depth']")
            if not bottom_depth_input:
                self.logger.error("Bottom Depth Input Field Not Found")
                return False

            if not self.enter_text(bottom_depth_input, "60", "Bottom Depth field"):
                return False

            time.sleep(3)
            
            # 19. Select "Inches" radio button
            self.logger.info("Selecting 'Inches' radio button...")
            inches_radio = self.wait_for_element("input[name='Units_of_Measure'][value='Inches']")
            if not inches_radio:
                self.logger.error("Inches radio button not found")
                return False

            if not self.click_element(inches_radio, "Inches radio button"):
                return False
            
            time.sleep(3)

            # 20. Click the "View Rating" button
            self.logger.info("Clicking View Rating button...")
            view_rating_button = self.wait_for_element_clickable("#ParameterForm15ViewRating_bottom")
            if not view_rating_button:
                self.logger.error("View Rating button not found or not clickable")
                return False

            if not self.click_element(view_rating_button, "View Rating button"):
                return False

            # Wait longer for ratings to load as this likely triggers a data fetch/calculation
            self.logger.info("Waiting for ratings to load...")
            time.sleep(12)
            
            self.logger.info("Ratings loaded")

            # 21. Click the "Printable Version" button
            self.logger.info("Clicking Printable Version button...")
            printable_version_button = self.wait_for_element_clickable("#controlbarprintbibid_unfold")
            if not printable_version_button:
                self.logger.error("Printable Version button not found or not clickable")
                return False

            if not self.click_element(printable_version_button, "Printable Version button"):
                return False

            # Wait for the printable version options to load/expand
            time.sleep(3)
            
            # 22. Enter the address into the Custom Subtitle field
            self.logger.info("Entering address into Custom Subtitle field...")
            subtitle_field = self.wait_for_element("input[name='subtitle']")
            if not subtitle_field:
                self.logger.error("Custom Subtitle field not found")
                return False

            if not self.enter_text(subtitle_field, address, "Custom Subtitle field"):
                return False

            time.sleep(2)

            # 23. Click the View button to generate PDF
            self.logger.info("Clicking View button to generate PDF...")
            view_button = self.wait_for_element_clickable("#controlbarprintbibid_submit_button")
            if not view_button:
                self.logger.error("View button not found or not clickable")
                return False

            if not self.click_element(view_button, "View PDF button"):
                return False

            # Wait longer as this will generate and open a PDF
            self.logger.info("Waiting for PDF to generate...")
            time.sleep(30)
            
            # 24. Scroll the window
            self.logger.info("Scrolling down to see additional options. . .")
            if not self.scroll_window(500):
                self.logger.warning("Failed to scroll window")
                
            time.sleep(3)
            
            # 25. click Soil qualities and features
            self.logger.info("Clicking Soil Quality and Features Button. . .")
            soil_qual_button = self.wait_for_element_clickable("#Soil_Qualities_and_Features_unfold")
            if not soil_qual_button:
                self.logger.error("Linear Extensability button not found")
                return False
            
            if not self.click_element(soil_qual_button, "Soil Qualities Button"):
                return False
            
            time.sleep(5)
            
            # 26. Scroll the window
            self.logger.info("Scrolling down to see additional options. . .")
            if not self.scroll_window(300):
                self.logger.warning("Failed to scroll window")
                
            time.sleep(2)
            
            # 27. click Soil qualities and features
            self.logger.info("Clicking Unified Soil Classification Button. . .")
            soil_class_button = self.wait_for_element_clickable("#Soil_Qualities_and_Features_Unified_Soil_Classification_\.40\.Surface\.41\._header > span > span")
            if not soil_class_button:
                self.logger.error("Unified Soil Classiciation button not found")
                return False
            
            if not self.click_element(soil_class_button, "Unified Souls Classification Button"):
                return False
            
            time.sleep(5)
            
            # 28. click view rating
            self.logger.info("Clicking view ratings Button Second Time. . .")
            soil_class_rating_button = self.wait_for_element_clickable("#ParameterForm381ViewRating_top")
            if not soil_class_rating_button:
                self.logger.error("rating button not found")
                return False
            
            if not self.click_element(soil_class_rating_button, "Rating Button"):
                return False
            
            time.sleep(5)
            
            # 29. Scroll back up to access the printable version
            self.logger.info("Scrolling up to see additional options. . .")
            if not self.scroll_window(-900):
                self.logger.warning("Failed to scroll window")
                
            time.sleep(2)
            
            # 30. Click the "Printable Version" button
            self.logger.info("Clicking Printable Version Second Time ...")
            printable_version_button_two = self.wait_for_element_clickable("#controlbarprintbibid_unfold")
            if not printable_version_button_two:
                self.logger.error("Printable Version button not found or not clickable")
                return False

            if not self.click_element(printable_version_button_two, "Printable Version button"):
                return False

            # Wait for the printable version options to load/expand
            time.sleep(3)
            
            # 23. Click the View button to generate PDF
            self.logger.info("Clicking View button to generate PDF...")
            view_button_two = self.wait_for_element_clickable("#controlbarprintbibid_submit_button")
            if not view_button_two:
                self.logger.error("View button not found or not clickable")
                return False

            if not self.click_element(view_button_two, "View PDF button"):
                return False

            # Wait longer as this will generate and open a PDF
            self.logger.info("Waiting for PDF to generate...")
            time.sleep(30)
    
            self.logger.info("Initial workflow completed successfully")
            return True
        
        except Exception as e:
            self.logger.error(f"Error during initial workflow: {str(e)}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.logger.info("WebDriver closed")
                
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
