import sys
import os
from PyQt5.QtWidgets import (
    QMainWindow, QHBoxLayout, QWidget, QPushButton, QVBoxLayout, QTextEdit, QStackedWidget
)
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView

# Import the DetailsWidget
from Front_End.views.details_widget import DetailsWidget

# Import controllers
from Front_End.controllers.auth_controller import AuthController
from Front_End.controllers.project_controller import ProjectController
from Front_End.controllers.report_controller import ReportController
from Front_End.controllers.ahj_controller import AHJController
from Front_End.controllers.cover_letter_controller import CoverLetterController
from Front_End.controllers.update_address_controller import UpdateAddressController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SML Report Generator")
        self.resize(1000, 700)

        # Initialize controllers
        self.auth_controller = AuthController(self)
        self.project_controller = ProjectController(self)
        self.report_controller = ReportController(self)
        self.ahj_controller = AHJController(self)
        self.cover_letter_controller = CoverLetterController(self)
        self.update_address_controller = UpdateAddressController(self)

        # Setup UI components
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        # Main layout
        main_layout = QHBoxLayout()

        # Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar.setLayout(sidebar_layout)

        # Buttons
        self.login_button = QPushButton("Login && Authenticate")
        self.retrieve_button = QPushButton("Retrieve Projects")
        self.update_address_button = QPushButton("Update Project Address")
        self.ahj_button = QPushButton("Find AHJ && Amendments")
        self.report_button = QPushButton("Export Project Details")
        self.cover_sheet_button = QPushButton("Create Cover Sheet")
        self.exit_button = QPushButton("Exit")

        # Set button styles
        for button in [
            self.login_button, self.retrieve_button, self.update_address_button, self.ahj_button,
            self.report_button, self.cover_sheet_button, self.exit_button
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

        # Welcome message when application launches
        welcome_message = """
        Welcome to the SML Report Generator!\n
        If this is your first time using the application, you must first select 'Login & Authenticate' to add your credentials to the database.\n
        If you have already used the program, you can select your email from the drop-down when you select 'Retrieve Projects'.
        """
        self.message_area.append(welcome_message)

        # Project/client details display area
        self.details_widget = DetailsWidget(self)

        # Add views to the display area:
        self.display_area.addWidget(self.message_area)  # index 0
        self.display_area.addWidget(self.browser)       # index 1
        self.display_area.addWidget(self.details_widget)  # index 2

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

    def connect_signals(self):
        # Connect buttons to controller methods
        self.login_button.clicked.connect(self.auth_controller.login)
        self.retrieve_button.clicked.connect(self.project_controller.retrieve_projects)
        self.ahj_button.clicked.connect(self.ahj_controller.run_ahj_finder)
        self.report_button.clicked.connect(self.report_controller.create_report)
        self.cover_sheet_button.clicked.connect(self.cover_letter_controller.create_cover_sheet)
        self.update_address_button.clicked.connect(self.update_address_controller.run_update_address)
        self.exit_button.clicked.connect(self.close)

        # Connect browser URL changes to auth controller
        self.browser.urlChanged.connect(self.auth_controller.on_url_changed)

        # Connect signals from DetailsWidget buttons
        self.details_widget.back_button.clicked.connect(self.project_controller.go_back_to_project_retrieval)
        self.details_widget.confirm_button.clicked.connect(self.project_controller.confirm_project)

