from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

class UpdateAddressWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        label = QLabel("Update Project Address")
        label.setStyleSheet("font-weight: bold; font-size: 18px;")
        layout.addWidget(label)

        self.start_button = QPushButton("Start Update Process")
        layout.addWidget(self.start_button)

        self.setLayout(layout)
