from PyQt5.QtCore import QUrl
from urllib.parse import urlparse
from PyQt5.QtWidgets import QMessageBox

class AuthController:
    def __init__(self, main_window):
        self.main_window = main_window  # Reference to MainWindow to interact with UI

    def login(self):
        # Load the login URL in the browser
        login_url = 'http://localhost:8000/login'
        self.main_window.browser.load(QUrl(login_url))
        self.main_window.display_area.setCurrentIndex(1)  # Show browser
        self.main_window.message_area.append("Please complete the login process in the browser.")

    def on_url_changed(self, url):
        url_str = url.toString()
        self.main_window.message_area.append(f"URL changed to: {url_str}")
        # Parse the URL to get the path
        parsed_url = urlparse(url_str)
        path = parsed_url.path

        if path == '/callback':
            # Login process is complete
            self.main_window.message_area.append("Login process completed.")
            self.main_window.display_area.setCurrentIndex(0)  # Switch back to message area
        elif path == '/login_success':
            # Handle successful login if you redirect to /login_success
            self.main_window.message_area.append("Login successful page loaded.")
