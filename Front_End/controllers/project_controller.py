from PyQt5.QtWidgets import QInputDialog, QMessageBox
from Front_End.models.project_model import Project
from Front_End.models.client_model import Client
from Back_End.database import (
    get_all_emails_and_subs, get_sub_by_email
)
from Back_End.project_manager import (
    get_project_by_code, extract_client_id, get_client_by_id,
    extract_project_address, extract_project_details, extract_client_address, extract_client_details
)

class ProjectController:
    def __init__(self, main_window):
        self.main_window = main_window  # Reference to MainWindow to update UI

    def retrieve_projects(self):
        # Switch to message area
        self.main_window.display_area.setCurrentIndex(0)
        self.main_window.message_area.append("\nRetrieve Project")

        # Get all emails and subs from database
        users = get_all_emails_and_subs()
        if not users:
            self.main_window.message_area.append("No users found in the database. Please Authenticate First")
            return

        # Display list of users and get selection
        emails = [email for email, _ in users]
        selected_email, ok = QInputDialog.getItem(
            self.main_window, "Select User", "Available Users:", emails, 0, False
        )
        if not ok or not selected_email:
            self.main_window.message_area.append("No user selected.")
            return

        # Map email to sub
        selected_sub = get_sub_by_email(selected_email)
        if not selected_sub:
            self.main_window.message_area.append("Could not find user information.")
            return

        self.main_window.message_area.append(f"The selected email is: {selected_email}")

        # Show helpful prompt about formatting the Project ID
        formatting_message = """
        Leading/Trailing zeros must be included in the Project ID.
        For example:
        ID 1 should be 0001-17 or 24-0001
        ID 12 should be 012-17 or 24-012
        ID 319 should be 0319-17 or 24-0319
        ID 1067 should be 1067-17 or 24-1067
        """
        self.main_window.message_area.append(formatting_message)

        # Get project code from user
        project_code, ok = QInputDialog.getText(
            self.main_window, "Project Code",
            "Enter the Project ID (e.g., 0182-22 or 24-0189):"
        )
        if not ok or not project_code:
            self.main_window.message_area.append("No project code entered.")
            return

        # Store project_code to be used when saving workbook
        self.main_window.project_code = project_code

        # Retrieve project data
        project_data = get_project_by_code(project_code, selected_email)
        if not project_data:
            self.main_window.message_area.append("No project data found.")
            return
        
        project = Project.from_dict(project_data[0])
        # check if address is missing
        if not project.street1 and not project.city and not project.state:
            self.main_window.message_area.append(
                "This project does not have an address. "
                "Please use the 'Update Project Address' button before creating the report."
            )
            return
        
        # Retrieve client data
        client_data = get_client_by_id(project.client_id, selected_email)
        if not client_data:
            self.main_window.message_area.append("No client data found.")
            return

        # Create Client instance
        client = Client.from_dict(client_data[0])

        # Store the models in main_window for later use
        self.main_window.project = project
        self.main_window.client = client

        # Update the UI with model data
        details_widget = self.main_window.details_widget

        # Project Details
        details_widget.project_id_value.setText(project.code)
        details_widget.project_name_value.setText(project.name)
        details_widget.project_po_value.setText(project.purchase_order_number)
        details_widget.billing_contact_value.setText(project.billing_contact)

        # Client Details
        details_widget.client_name_value.setText(client.name)

        # Project Address
        details_widget.project_street1_value.setText(project.street1)
        details_widget.project_street2_value.setText(project.street2)
        details_widget.project_city_value.setText(project.city)
        details_widget.project_state_value.setText(project.state)
        details_widget.project_zip_value.setText(project.zip_code)

        # Client Address
        details_widget.client_street1_value.setText(client.street1)
        details_widget.client_street2_value.setText(client.street2)
        details_widget.client_city_value.setText(client.city)
        details_widget.client_state_value.setText(client.state)
        details_widget.client_zip_value.setText(client.zip_code)

        # Switch to the details display
        self.main_window.display_area.setCurrentIndex(2)
    
    def go_back_to_project_retrieval(self):
        """
        Action triggered when the back button is clicked, allowing the user to re-enter a project code.
        """
        # Clear the current data
        self.main_window.project = None
        self.main_window.client = None

        # Reset the DetailsWidget fields
        self.main_window.details_widget.clear_fields()

        # Prompt the user to enter a new project code
        self.retrieve_projects()

    def confirm_project(self):
        """
        Action triggered when the confirm button is clicked. The user confirms the project details,
        and the project/client information is retained for the next step.
        """
        # Switch back to the main message area
        self.main_window.display_area.setCurrentIndex(0)

        # Display confirmation in the message area
        self.main_window.message_area.append("\nProject and Client Details Confirmed:")
        self.main_window.message_area.append(f"Project Name: {self.main_window.project.name}")
        self.main_window.message_area.append(f"Client Name: {self.main_window.client.name}")
        self.main_window.message_area.append("\nNow you can proceed to find the AHJ and Amendments.")


