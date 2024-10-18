import requests
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QLabel
from PyQt5.QtCore import Qt
from Back_End import config
from Front_End.views.ahj_amendment_widget import AHJAmendmentWidget

class AHJController:
    def __init__(self, main_window):
        self.main_window = main_window  # Reference to MainWindow to interact with UI
    
    def run_ahj_finder(self):
        if not hasattr(self.main_window, 'project'):
            self.main_window.message_area.append("Project data not available. Please retrieve the project first.")
            return

        # Create project object
        project = self.main_window.project

        # Build address for AHJ search
        ahj_address_info = f"{project.street1}, {project.street2}, {project.city}, {project.state}, {project.zip_code}"

        self.main_window.message_area.append(f"Using project address for AHJ Finder: {ahj_address_info}")

        try:
            # Step 1: Send the project address to the AHJ Finder API to get AHJ info
            api_url = config.AHJ_LINK
            response = requests.post(api_url, json={'address': ahj_address_info})

            if response.status_code == 200:
                self.main_window.ahj_data = response.json().get('ahj_info', [])
                if self.main_window.ahj_data:
                    self.main_window.message_area.append("AHJ Information retrieved successfully!")

                    # Initialize amendment_data as empty list
                    self.main_window.amendment_data = []

                    # Step 2: Use the AHJ Name to retrieve building code amendments
                    ahj_name = self.main_window.ahj_data[0].get('AHJ Name')
                    if ahj_name:
                        amendment_url = config.AMEND_LINK
                        amend_response = requests.post(amendment_url, json={'ahj_name': ahj_name})

                        if amend_response.status_code == 200:
                            self.main_window.amendment_data = amend_response.json().get('amendments', [])
                            if self.main_window.amendment_data:
                                self.main_window.message_area.append(f"Amendments for {ahj_name} retrieved successfully.")
                            else:
                                self.main_window.message_area.append(f"No amendments found for {ahj_name}.")
                        else:
                            self.main_window.message_area.append(f"Failed to retrieve amendments. Status Code: {amend_response.status_code}")
                    else:
                        self.main_window.message_area.append("AHJ Name not available for amendment search.")

                    # Create and display the AHJAmendmentWidget
                    ahj_amendment_widget = AHJAmendmentWidget(self.main_window.ahj_data, self.main_window.amendment_data)
                    self.main_window.display_area.addWidget(ahj_amendment_widget)
                    self.main_window.display_area.setCurrentWidget(ahj_amendment_widget)

                else:
                    self.main_window.message_area.append("No AHJ information found.")
            else:
                self.main_window.message_area.append(f"Failed to retrieve AHJ info. Status Code: {response.status_code}")

        except Exception as e:
            self.main_window.message_area.append(f"Failed to interact with AHJ Finder API: {e}")

