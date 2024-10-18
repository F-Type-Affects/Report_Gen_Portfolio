from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt

class AHJAmendmentWidget(QWidget):
    def __init__(self, ahj_data, amendment_data):
        super().__init__()

        self.ahj_data = ahj_data
        self.amendment_data = amendment_data

        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

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
        layout.addWidget(ahj_table)

        # Create a table for Amendments if any
        if self.amendment_data:
            amendment_table = QTableWidget()
            amendment_table.setRowCount(len(self.amendment_data))
            amendment_table.setColumnCount(1)
            amendment_table.setHorizontalHeaderLabels(['Amendments'])
            amendment_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

            for row, link in enumerate(self.amendment_data):
                file_name = link.split('/')[-1]
                item = QTableWidgetItem(file_name)
                item.setData(Qt.UserRole, link)
                amendment_table.setItem(row, 0, item)

            # Add the amendment table to the layout
            layout.addWidget(amendment_table)
