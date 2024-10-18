import sys
import os
import re
import subprocess
import requests
from SML_Reports_Test.Back_End import config

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QVBoxLayout,
    QHBoxLayout, QTextEdit, QStackedWidget, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QIcon
import logging

# Import your existing modules
from SML_Reports_Test.Back_End.database import (
    get_all_emails_and_subs, get_sub_by_email, get_all_tokens_data
)
from .project_manager import (
    get_project_by_code, extract_client_id, get_client_by_id,
    extract_project_address, extract_project_details, extract_client_address, extract_client_details
)
from .export_project_details import (
    create_workbook, insert_project_data, insert_client_data, save_workbook, insert_ahj_data
)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Main Window Class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SML Report Generator")
        self.resize(1000, 700)

        # Main layout
        main_layout = QHBoxLayout()

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)

        # Buttons
        self.login_button = QPushButton("Login && Authenticate")
        self.retrieve_button = QPushButton("Retrieve Projects")
        self.ahj_button = QPushButton("Find AHJ && Ammendments")
        self.report_button = QPushButton("Create Report")
        self.exit_button = QPushButton("Exit")

        # Set button styles
        for button in [
            self.login_button, self.retrieve_button, self.ahj_button,
            self.report_button, self.exit_button
        ]:
            button.setFixedHeight(50)
            button.setStyleSheet("""
                QPushButton {
                    border-radius: 15px;
                    background-color: #007ACC;
                    color: white;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background-color: #005F9E;
                }
            """)
            sidebar_layout.addWidget(button)
            sidebar_layout.addSpacing(10)

        sidebar_layout.addStretch()

        # Main display area
        self.display_area = QStackedWidget()

        # Web browser view
        self.browser = QWebEngineView()

        # Message display area
        self.message_area = QTextEdit()
        self.message_area.setReadOnly(True)
        
        # welcome message when application launches
        welcome_message = """
        Welcome to the SML Report Generator!\n
        If this is your first time using the application, you must first select 'Login & Authenticate' to add your credentials to the database.\n
        If you have already used the program, you can select your email from the drop-down when you select 'Retrieve Projects'.
        """
        self.message_area.append(welcome_message)
        
        # Project/client details display area
        self.setup_details_widget()
        
        # Add views to the display area:
        self.display_area.addWidget(self.message_area) # index 0
        self.display_area.addWidget(self.browser) # index 1
        self.display_area.addWidget(self.details_widget) # index 2
        
        # Set initial view to message area
        self.display_area.setCurrentIndex(0)

        # Set layouts
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.display_area)

        # Set stretch factors to maintain 20% (sidebar) and 80% (display area)
        main_layout.setStretch(0, 1)  # Sidebar takes 1 part
        main_layout.setStretch(1, 4)  # Display area takes 4 parts

        # Central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Connect buttons to functions
        self.login_button.clicked.connect(self.login)
        self.retrieve_button.clicked.connect(self.retrieve_projects)
        self.ahj_button.clicked.connect(self.run_ahj_finder)
        self.report_button.clicked.connect(self.create_report)
        self.exit_button.clicked.connect(self.close)

        # Variables to hold data between functions
        self.project_detail_info = None
        self.project_address_info = None
        self.client_information = None
        self.client_address_info = None

        # Connect URL change signal to detect login completion
        self.browser.urlChanged.connect(self.on_url_changed)
    
    # opens web browser for login and authentication in main GUI window
    def login(self):
        # Load the login URL in the browser
        login_url = 'http://localhost:8000/login'
        self.browser.load(QUrl(login_url))
        self.display_area.setCurrentIndex(1)  # Show browser
        self.message_area.append("Please complete the login process in the browser.")

    def on_url_changed(self, url):
        url_str = url.toString()
        self.message_area.append(f"URL changed to: {url_str}")
        # Parse the URL to get the path
        from urllib.parse import urlparse
        parsed_url = urlparse(url_str)
        path = parsed_url.path
        
        if path == '/callback':
            # Login process is complete
            self.message_area.append("Login process completed.")
            self.display_area.setCurrentIndex(0)  # Switch back to message area
        elif path == '/login_success':
            # Handle successful login if you redirect to /login_success
            self.message_area.append("Login successful page loaded.")
            #self.display_area.setCurrentIndex(0)  # Switch back to message area
            
    def retrieve_projects(self):
        # Switch to message area
        self.display_area.setCurrentIndex(0)
        self.message_area.append("\nRetrieve Project")

        # Get all emails and subs from database
        users = get_all_emails_and_subs()
        if not users:
            self.message_area.append("No users found in the database. Please Authenticate First")
            return

        # Display list of users and get selection
        emails = [email for email, _ in users]
        selected_email, ok = QInputDialog.getItem(
            self, "Select User", "Available Users:", emails, 0, False
        )
        if not ok or not selected_email:
            self.message_area.append("No user selected.")
            return

        # Map email to sub
        selected_sub = get_sub_by_email(selected_email)
        if not selected_sub:
            self.message_area.append("Could not find user information.")
            return

        self.message_area.append(f"The selected email is: {selected_email}")
        
        # Show helpful prompt about formatting the Project ID
        formatting_message = """
        Leading/Trailing zeros must be included in the Project ID. 
        For example:
        ID 1 should be 0001-17 or 24-0001
        ID 12 should be 012-17 or 24-012
        ID 319 should be 0319-17 or 24-0319
        ID 1067 should be 1067-17 or 24-1067
        """
        self.message_area.append(formatting_message) 

        # Get project code from user
        project_code, ok = QInputDialog.getText(
            self, "Project Code",
            "Enter the Project ID (e.g., 0182-22 or 24-0189):"
        )
        if not ok or not project_code:
            self.message_area.append("No project code entered.")
            return
        
        #store project_code to be used when saving workbook
        self.project_code = project_code

        # Retrieve project data
        project_data = get_project_by_code(project_code, selected_email)
        if not project_data:
            self.message_area.append("No project data found.")
            return

        # Extract client ID
        client_id = extract_client_id(project_data)
        if not client_id:
            self.message_area.append("Could not extract client ID.")
            return

        # Get client data
        client_data = get_client_by_id(client_id, selected_email)
        if not client_data:
            self.message_area.append("No client data found.")
            return

        # Extract project and client details
        self.project_address_info = extract_project_address(project_data)
        self.project_detail_info = extract_project_details(project_data)
        self.client_address_info = extract_client_address(client_data)
        self.client_information = extract_client_details(client_data)
        
        # create formatted address to pass to AHJ finder
        self.ahj_address_info = f"{self.project_address_info.get('Street1', '')}, {self.project_address_info.get('Street2', '')}, {self.project_address_info.get('City', '')}, {self.project_address_info.get('State', '')}, {self.project_address_info.get('Zip', '')}"
        
        # Populate Project Details
        self.project_id_value.setText(self.project_detail_info.get('Project ID', ''))
        self.project_name_value.setText(self.project_detail_info.get('Project Name', ''))
        self.project_po_value.setText(str(self.project_detail_info.get('Project PO#', '')))
        self.billing_contact_value.setText(str(self.project_detail_info.get('Billing Contact', '')))

        # Populate Client Details
        self.client_name_value.setText(self.client_information.get('Client Name', ''))

        # Populate Project Address
        self.project_street1_value.setText(self.project_address_info.get('Street1', ''))
        self.project_street2_value.setText(self.project_address_info.get('Street2', ''))
        self.project_city_value.setText(self.project_address_info.get('City', ''))
        self.project_state_value.setText(self.project_address_info.get('State', ''))
        self.project_zip_value.setText(self.project_address_info.get('Zip', ''))

        # Populate Client Address
        self.client_street1_value.setText(self.client_address_info.get('Street1', ''))
        self.client_street2_value.setText(self.client_address_info.get('Street2', ''))
        self.client_city_value.setText(self.client_address_info.get('City', ''))
        self.client_state_value.setText(self.client_address_info.get('State', ''))
        self.client_zip_value.setText(self.client_address_info.get('Zip', ''))

        # Switch to the details display
        self.display_area.setCurrentIndex(2)  # Index of the details widget

    def create_report(self):
        # Switch to message area
        self.display_area.setCurrentIndex(0)
        self.message_area.append("\nCreate Report")

        # Check if we have the necessary data
        if not all([
            self.project_detail_info, self.project_address_info,
            self.client_information, self.client_address_info, hasattr(self, 'project_code')
        ]):
            self.message_area.append("No project or client data available. Please retrieve projects first.")
            return

        # Create Excel workbook for report
        report_workbook = create_workbook()
        report_sheet = report_workbook.active

        # Insert project/client data
        insert_project_data(report_sheet, self.project_detail_info, self.project_address_info)
        insert_client_data(report_sheet, self.client_information, self.client_address_info)
        
        # insert ahj & ammendment data
        if hasattr(self, 'ahj_data') and hasattr(self, 'amendment_data'):
            insert_ahj_data(report_sheet, self.ahj_data, self.amendment_data)
        
        # find the directory
        project_code = self.project_code
        
        # normalize the project code to match directory format
        try:
            normalized_code, job_number, year_suffix = self.normalize_project_code(project_code)
        except ValueError as e:
            self.message_area.append(f"Error normalizing project code: {e}")
            return
        
        # set directory path
        report_directory = config.REPORT_DIRECTORY
        year_directory = os.path.join(report_directory, f"Jobs 20{year_suffix}")
                
        # check the directories exist
        if not os.path.isdir(year_directory):
            self.message_area.append(f"Year directory does not exist: {year_directory}")
            return
        
        # search for the job in the year directory
        job_dir = None
        for dir_name in os.listdir(year_directory):
            dir_path = os.path.join(year_directory, dir_name)
            if not os.path.isdir(dir_path):
                continue
        
            # normalize codes for comparision
            dir_code = dir_name[:6].strip()
            # remove non digit characters and leading zeros
            dir_code_digits = re.sub(r'\D', '', dir_code).lstrip('0')
            normalized_code_digits = re.sub(r'\D', '', normalized_code).lstrip('0')
            print(f"Checking directory: {dir_name}")
            print(f"dir_code_digits: {dir_code_digits}, normalized_code_digits: {normalized_code_digits}")
            
            if dir_code_digits == normalized_code_digits:
                job_dir = dir_path
                break
            
        if not job_dir:
            self.message_area.append(f"The dir_code is: {dir_code_digits}")
            self.message_area.append(f"The normalized_code_digits is: {normalized_code_digits}")
            self.message_area.append(f"Job directory not found for project code: {normalized_code} in {year_directory}")
            return
        
        # confirm the correct directory
        confirm = QMessageBox.question(
            self,
            "confirm Directory: ",
            f"Found job directory:\n\n{job_dir}\n\nIs this correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if confirm == QMessageBox.No:
            self.message_area.append("Job directory confirmation failed")
            
        # check for Project_Reports directory
        reports_dir = os.path.join(job_dir, "Project_Reports")
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
            
        # construct the file name
        project_name = self.project_detail_info.get('Project Name', 'Unknown Name')
        stripped_project_name = project_name.replace('/', ' ')
        file_name = f"{normalized_code} {stripped_project_name}.xlsx"
        
        # full path to save the workbook
        full_path = os.path.join(reports_dir, file_name)
        
        # Save the workbook
        save_result = save_workbook(report_workbook, full_path)

        if save_result:
            self.message_area.append(f"Report Created and saved at {full_path}")
        else:
            self.message_area.append("Failed to save workbook")

    def token_management(self):
        # Switch to message area
        self.display_area.setCurrentIndex(0)
        self.message_area.append("\nToken Management")

        # Get the token data and display it
        token_data = get_all_tokens_data()
        if token_data:
            headers = ["sub", "email", "id_token", "access_token", "expires_in", "token_type", "refresh_token", "refresh_token_expires_in"]
            self.message_area.append(" | ".join(headers))
            for row in token_data:
                self.message_area.append(" | ".join(str(item) for item in row))
        else:
            self.message_area.append("No token data found.")
    
    def setup_details_widget(self):
        self.details_widget = QWidget()
        layout = QVBoxLayout()
        
        # Project Details Title
        project_details_label = QLabel("Project Details:")
        project_details_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(project_details_label)
        
        # Project Details Field
        self.project_id_value = QLineEdit()
        self.project_id_value.setReadOnly(True)
        layout.addWidget(QLabel("Project ID:"))
        layout.addWidget(self.project_id_value)
        
        self.project_name_value = QLineEdit()
        self.project_name_value.setReadOnly(True)
        layout.addWidget(QLabel("Project Name:"))
        layout.addWidget(self.project_name_value)

        self.project_po_value = QLineEdit()
        self.project_po_value.setReadOnly(True)
        layout.addWidget(QLabel("Project PO#:"))
        layout.addWidget(self.project_po_value)

        self.billing_contact_value = QLineEdit()
        self.billing_contact_value.setReadOnly(True)
        layout.addWidget(QLabel("Billing Contact:"))
        layout.addWidget(self.billing_contact_value)

        # Client Details Title
        client_details_label = QLabel("Client Details:")
        client_details_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(client_details_label)

        self.client_name_value = QLineEdit()
        self.client_name_value.setReadOnly(True)
        layout.addWidget(QLabel("Client Name:"))
        layout.addWidget(self.client_name_value)

        # Addresses in a horizontal layout
        address_layout = QHBoxLayout()

        # Project Address Layout
        project_address_layout = QVBoxLayout()
        project_address_title = QLabel("Project Address:")
        project_address_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        project_address_layout.addWidget(project_address_title)

        self.project_street1_value = QLineEdit()
        self.project_street1_value.setReadOnly(True)
        project_address_layout.addWidget(QLabel("Street 1:"))
        project_address_layout.addWidget(self.project_street1_value)

        self.project_street2_value = QLineEdit()
        self.project_street2_value.setReadOnly(True)
        project_address_layout.addWidget(QLabel("Street 2:"))
        project_address_layout.addWidget(self.project_street2_value)

        self.project_city_value = QLineEdit()
        self.project_city_value.setReadOnly(True)
        project_address_layout.addWidget(QLabel("City:"))
        project_address_layout.addWidget(self.project_city_value)

        self.project_state_value = QLineEdit()
        self.project_state_value.setReadOnly(True)
        project_address_layout.addWidget(QLabel("State:"))
        project_address_layout.addWidget(self.project_state_value)

        self.project_zip_value = QLineEdit()
        self.project_zip_value.setReadOnly(True)
        project_address_layout.addWidget(QLabel("Zip:"))
        project_address_layout.addWidget(self.project_zip_value)

        address_layout.addLayout(project_address_layout)

        # Client Address Layout
        client_address_layout = QVBoxLayout()
        client_address_title = QLabel("Client Address:")
        client_address_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        client_address_layout.addWidget(client_address_title)

        self.client_street1_value = QLineEdit()
        self.client_street1_value.setReadOnly(True)
        client_address_layout.addWidget(QLabel("Street 1:"))
        client_address_layout.addWidget(self.client_street1_value)

        self.client_street2_value = QLineEdit()
        self.client_street2_value.setReadOnly(True)
        client_address_layout.addWidget(QLabel("Street 2:"))
        client_address_layout.addWidget(self.client_street2_value)

        self.client_city_value = QLineEdit()
        self.client_city_value.setReadOnly(True)
        client_address_layout.addWidget(QLabel("City:"))
        client_address_layout.addWidget(self.client_city_value)

        self.client_state_value = QLineEdit()
        self.client_state_value.setReadOnly(True)
        client_address_layout.addWidget(QLabel("State:"))
        client_address_layout.addWidget(self.client_state_value)

        self.client_zip_value = QLineEdit()
        self.client_zip_value.setReadOnly(True)
        client_address_layout.addWidget(QLabel("Zip:"))
        client_address_layout.addWidget(self.client_zip_value)

        address_layout.addLayout(client_address_layout)

        # Add the address layout to the main layout
        layout.addLayout(address_layout)

        # Add a back button and confirm button
        self.back_button = QPushButton("Back")
        self.confirm_button = QPushButton("Confirm Details")
        
        # connect the button
        self.back_button.clicked.connect(self.go_back_to_project_retrieval)
        self.confirm_button.clicked.connect(self.confirm_project)
        
        # add buttons to layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.confirm_button)
        layout.addLayout(button_layout)

        # Set the layout to the details widget
        self.details_widget.setLayout(layout)
        
    def go_back_to_main(self):
        self.display_area.setCurrentIndex(0)  # Switch back to the message area

    def normalize_project_code(self, project_code):
        parts = project_code.split('-')
        if len(parts) != 2:
            raise ValueError(f"Invalid project code format: {project_code}")
        part1, part2 = parts
        if len(part2) == 2 and len(part1) > 2:
            # Assume format is xxxx-yy
            job_number = part1
            year_suffix = part2
        elif len(part1) == 2 and len(part2) > 2:
            # Assume format is yy-xxxx, rearrange
            job_number = part2
            year_suffix = part1
        else:
            raise ValueError(f"Cannot determine format of project code: {project_code}")
        # Return normalized code in format xxxx-yy
        normalized_code = f"{job_number}-{year_suffix}"
        return normalized_code, job_number, year_suffix

    def run_ahj_finder(self):
        if not self.project_address_info:
            self.message_area.append("Project address not available. Please retrieve the project first.")
            return

        self.message_area.append(f"Using project address for AHJ Finder: {self.ahj_address_info}")
        
        try:
            # Step 1: Send the project address to the AHJ Finder API to get AHJ info
            api_url = config.AHJ_LINK
            response = requests.post(api_url, json={'address': self.ahj_address_info})
        
            if response.status_code == 200:
                self.ahj_data = response.json().get('ahj_info', [])
                if self.ahj_data:
                    self.message_area.append("AHJ Information retrieved successfully!")
                    
                    
                    # Create a QWidget to hold both tables
                    ahj_amendment_widget = QWidget()
                    ahj_amendment_layout = QVBoxLayout(ahj_amendment_widget)
                    
                    # Create a table for AHJ information
                    ahj_table = QTableWidget()
                    ahj_table.setRowCount(len(self.ahj_data))
                    ahj_table.setColumnCount(2)
                    ahj_table.setHorizontalHeaderLabels(['AHJ Name', 'Building Code'])
                    ahj_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                    
                    for row, ahj in enumerate(self.ahj_data):
                        ahj_name = ahj.get('AHJ Name', '')
                        building_code = ahj.get('Building Code', '')
                        
                        ahj_table.setItem(row, 0, QTableWidgetItem(ahj_name))
                        ahj_table.setItem(row, 1, QTableWidgetItem(building_code))
                    
                    # Add the AHJ table to the layout
                    ahj_amendment_layout.addWidget(ahj_table)
                    
                else:
                    self.message_area.append("No AHJ information found.")
            else:
                self.message_area.append(f"Failed to retrieve AHJ info. Status Code: {response.status_code}")

            # Step 2: Use the AHJ Name to retrieve building code amendments
            if self.ahj_data:
                ahj_name = self.ahj_data[0].get('AHJ Name')
                if ahj_name:
                    amendment_url = config.AMMEND_LINK
                    amend_response = requests.post(amendment_url, json={'ahj_name': ahj_name})

                    if amend_response.status_code == 200:
                        self.amendment_data = amend_response.json().get('amendments', [])
                        if self.amendment_data:
                            self.message_area.append(f"Amendments for {ahj_name}:")

                            # Create a table for Amendments
                            amendment_table = QTableWidget()
                            amendment_table.setRowCount(len(self.amendment_data))
                            amendment_table.setColumnCount(1)
                            amendment_table.setHorizontalHeaderLabels([f"Amendments for {ahj_name}"])
                            amendment_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

                            for row, link in enumerate(self.amendment_data):
                                # Extract the file name from the link
                                file_name = link.split('/')[-1]
                                item = QTableWidgetItem(file_name)
                                item.setData(Qt.UserRole, link)  # Store the link as user data
                                amendment_table.setItem(row, 0, item)

                            # Add the amendment table to the layout
                            ahj_amendment_layout.addWidget(amendment_table)

                        else:
                            self.message_area.append(f"No amendments found for {ahj_name}.")
                    else:
                        self.message_area.append(f"Failed to retrieve amendments. Status Code: {amend_response.status_code}")
                else:
                    self.message_area.append("AHJ Name not available for amendment search.")
                    
            # Add the AHJ and Amendment widget to the display area
            self.display_area.addWidget(ahj_amendment_widget)
            self.display_area.setCurrentWidget(ahj_amendment_widget)
        except Exception as e:
            self.message_area.append(f"Failed to interact with AHJ Finder API: {e}")            
    
    def go_back_to_project_retrieval(self):
        """
        Action triggered when the back button is clicked, allowing the user to re-enter a project code.
        """
        # Clear the current data
        self.project_detail_info = None
        self.project_address_info = None
        self.client_information = None
        self.client_address_info = None

        # Prompt the user to enter a new project code
        self.retrieve_projects()

    def confirm_project(self):
        """
        Action triggered when the confirm button is clicked. The user confirms the project details,
        and the project/client information is retained for the next step.
        """
        # Hide the project details and switch back to the main window
        self.display_area.setCurrentIndex(0)  # Switch to main message area

        # Display confirmation in the message area
        self.message_area.append("\nProject and Client Details Confirmed:")
        self.message_area.append(f"Project Name: {self.project_name_value.text()}")
        self.message_area.append(f"Client Name: {self.client_name_value.text()}")
        self.message_area.append("\nNow you can proceed to find the AHJ and Amendments.")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
