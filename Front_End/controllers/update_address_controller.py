from PyQt5.QtWidgets import QInputDialog, QMessageBox, QVBoxLayout, QLineEdit, QWidget, QPushButton, QLabel, QHBoxLayout
from Back_End.update_project_address import get_project_address_by_code, update_project_address_in_bqe
from Back_End.database import get_all_emails_and_subs
from Back_End import config
import requests
import re

class UpdateAddressController:
    def __init__(self, main_window):
        self.main_window = main_window

    def run_update_address(self):
        """Start the address update process."""
        # Prompt for user email
        users = get_all_emails_and_subs()
        if not users:
            self.main_window.message_area.append("No users found in the database.")
            return

        emails = [email for email, _ in users]
        selected_email, ok = QInputDialog.getItem(
            self.main_window, "Select User", "Available Users:", emails, 0, False
        )
        if not ok or not selected_email:
            self.main_window.message_area.append("No user selected.")
            return

        # Prompt for project code
        project_code, ok = QInputDialog.getText(
            self.main_window, "Project Code", 
            "Enter the Project ID (e.g., 0182-22 or 24-0189):"
        )
        if not ok or not project_code:
            self.main_window.message_area.append("No project code entered.")
            return

        # Retrieve project details only once here
        project_data = get_project_address_by_code(project_code, selected_email)
        if project_data and 'memo' in project_data[0]:
            self.confirm_memo_address(project_data[0], selected_email)  # Pass entire project_data object
        else:
            self.prompt_manual_address_entry(project_data[0]['id'])

    def confirm_memo_address(self, project_data, selected_email):
        """Display the memo and ask for confirmation to search Bing."""
        memo = project_data['memo']
        
        # Show memo for confirmation first
        address_layout = QVBoxLayout()
        address_layout.addWidget(QLabel(f"Memo Content: {memo}"))
        
        confirm_button = QPushButton("Search Address via Bing")
        confirm_button.clicked.connect(lambda: self.bing_search_for_address(memo, project_data, selected_email))

        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: self.main_window.display_area.setCurrentIndex(0))
        
        button_layout = QHBoxLayout()
        button_layout.addWidget(back_button)
        button_layout.addWidget(confirm_button)
        
        address_layout.addLayout(button_layout)
        address_widget = QWidget()
        address_widget.setLayout(address_layout)
        self.main_window.display_area.addWidget(address_widget)
        self.main_window.display_area.setCurrentWidget(address_widget)
    
    def bing_search_for_address(self, memo, project_data, selected_email):
        """Use Bing Web Search API to get address details from memo."""
        print(f"Search initiated with memo: {memo}")
        subscription_key = config.BING_KEY
        search_url = f"{config.BING_ENDPOINT}v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": subscription_key}
        params = {"q": memo, "mkt": "en-US"}  # Searching the memo content

        try:
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            search_results = response.json()
            
            print(f"Search results: {search_results}")

            # Process search results from web search to extract an address
            if 'webPages' in search_results and 'value' in search_results['webPages']:
                # Loop through the top results and try to parse addresses
                for result in search_results['webPages']['value']:
                    snippet = result.get('snippet', '')
                    # Example: you can implement regex parsing on snippet to extract address info
                    address = self.extract_address_from_snippet(snippet)
            
                    if address:
                        print(f"Address found: {address}")
                        # If address found, confirm and update the project
                        self.display_bing_address_confirmation(address, project_data, selected_email)
                        return address

            return None  # No valid address found
        except requests.exceptions.RequestException as e:
            print(f"Error while searching Bing: {e}")
            return None

    
    def extract_address_from_snippet(self, snippet):
        """Extract address from the search snippet using a simple regex."""
        # You can refine this with regex to better parse street, city, state, zip
        # A very basic example regex pattern that you might enhance
        address_pattern = re.compile(r'(\d+\s[\w\s]+),\s([\w\s]+),\s([A-Z]{2}),\s(\d{5})')
        match = address_pattern.search(snippet)
    
        if match:
            return {
                'street1': match.group(1),
                'street2': '',
                'city': match.group(2),
                'state': match.group(3),
                'zip': match.group(4)
            }
        return None
    
    def display_bing_address_confirmation(self, address, project_data, selected_email):
        """Display the Bing returned address for user confirmation."""
        address_layout = QVBoxLayout()

        address_layout.addWidget(QLabel(f"Street 1: {address['street1']}"))
        address_layout.addWidget(QLabel(f"Street 2: {address['street2']}"))
        address_layout.addWidget(QLabel(f"City: {address['city']}"))
        address_layout.addWidget(QLabel(f"State: {address['state']}"))
        address_layout.addWidget(QLabel(f"Zip: {address['zip']}"))

        confirm_button = QPushButton("Confirm Address")
        confirm_button.clicked.connect(lambda: self.confirm_address(project_data, address, selected_email))
        
        manual_update_button = QPushButton("Update Address Manually")
        manual_update_button.clicked.connect(lambda: self.prompt_manual_address_entry(project_data['id']))

        back_button = QPushButton("Back")
        back_button.clicked.connect(lambda: self.main_window.display_area.setCurrentIndex(0))

        button_layout = QHBoxLayout()
        button_layout.addWidget(back_button)
        button_layout.addWidget(manual_update_button)
        button_layout.addWidget(confirm_button)
        
        address_layout.addLayout(button_layout)
        address_widget = QWidget()
        address_widget.setLayout(address_layout)
        self.main_window.display_area.addWidget(address_widget)
        self.main_window.display_area.setCurrentWidget(address_widget)
    
    def confirm_address(self, project_data, address, selected_email):
        """Handle the confirmed address."""
        # Pass project_data and address directly
        update_project_address_in_bqe(project_data, address, selected_email)
        QMessageBox.information(self.main_window, "Success", "Address updated successfully!")
        self.main_window.display_area.setCurrentIndex(0)
    

    def prompt_manual_address_entry(self, project_id):
        """Prompt the user to enter the address manually."""
        self.manual_address_widget = ManualAddressWidget(self.main_window, project_id)
        self.main_window.display_area.addWidget(self.manual_address_widget)
        self.main_window.display_area.setCurrentWidget(self.manual_address_widget)

class ManualAddressWidget(QWidget):
    def __init__(self, parent, project_id):
        super().__init__(parent)
        self.project_id = project_id
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        self.street1_input = QLineEdit()
        self.street2_input = QLineEdit()
        self.city_input = QLineEdit()
        self.state_input = QLineEdit()
        self.zip_input = QLineEdit()

        update_button = QPushButton("Update Address")
        update_button.clicked.connect(self.update_address)

        layout.addWidget(QLabel("Street 1:"))
        layout.addWidget(self.street1_input)
        layout.addWidget(QLabel("Street 2:"))
        layout.addWidget(self.street2_input)
        layout.addWidget(QLabel("City:"))
        layout.addWidget(self.city_input)
        layout.addWidget(QLabel("State:"))
        layout.addWidget(self.state_input)
        layout.addWidget(QLabel("Zip:"))
        layout.addWidget(self.zip_input)
        layout.addWidget(update_button)

        self.setLayout(layout)

    def update_address(self):
        """Update the address using manual input."""
        address = {
            'street1': self.street1_input.text(),
            'street2': self.street2_input.text(),
            'city': self.city_input.text(),
            'state': self.state_input.text(),
            'zip': self.zip_input.text()
        }
        update_project_address_in_bqe(self.project_id, address)
        QMessageBox.information(self, "Success", "Address updated successfully!")
