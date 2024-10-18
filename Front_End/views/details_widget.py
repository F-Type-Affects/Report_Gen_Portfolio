from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QPushButton
)

class DetailsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Project Details Title
        project_details_label = QLabel("Project Details:")
        project_details_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(project_details_label)

        # Project Details Fields
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

        # Add Back and Confirm buttons
        self.back_button = QPushButton("Back")
        self.confirm_button = QPushButton("Confirm Details")

        # You can connect these buttons to methods or controller actions later
        # self.back_button.clicked.connect(...)
        # self.confirm_button.clicked.connect(...)

        # Add buttons to layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.back_button)
        button_layout.addWidget(self.confirm_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
    
    def clear_fields(self):
        # Clear Project Details
        self.project_id_value.clear()
        self.project_name_value.clear()
        self.project_po_value.clear()
        self.billing_contact_value.clear()

        # Clear Client Details
        self.client_name_value.clear()

        # Clear Project Address
        self.project_street1_value.clear()
        self.project_street2_value.clear()
        self.project_city_value.clear()
        self.project_state_value.clear()
        self.project_zip_value.clear()

        # Clear Client Address
        self.client_street1_value.clear()
        self.client_street2_value.clear()
        self.client_city_value.clear()
        self.client_state_value.clear()
        self.client_zip_value.clear()
