import os
import re
from PyQt5.QtWidgets import QMessageBox
from Back_End import config
from Front_End.utils.export_project_details import (
    create_workbook, insert_project_data, insert_client_data, save_workbook, insert_ahj_data
)

class ReportController:
    def __init__(self, main_window):
        self.main_window = main_window  # Reference to MainWindow to interact with UI

    def create_report(self):
        # Switch to message area
        self.main_window.display_area.setCurrentIndex(0)
        self.main_window.message_area.append("\nCreate Report")

        # Check if we have the necessary data
        if not all([
            hasattr(self.main_window, 'project'), hasattr(self.main_window, 'client')
        ]):
            self.main_window.message_area.append("No project or client data available. Please retrieve projects first.")
            return

        # Access the models
        project = self.main_window.project
        client = self.main_window.client

        # Create Excel workbook for report
        report_workbook = create_workbook()
        report_sheet = report_workbook.active

        # Insert project/client data using models
        insert_project_data(report_sheet, project)
        insert_client_data(report_sheet, client)

        # Insert AHJ & Amendment data if available
        if hasattr(self.main_window, 'ahj_data') and hasattr(self.main_window, 'amendment_data'):
            insert_ahj_data(report_sheet, self.main_window.ahj_data, self.main_window.amendment_data)

        # Find the directory
        project_code = project.code  # Get project_code from project model

        # Normalize the project code to match directory format
        try:
            normalized_code, job_number, year_suffix = self.normalize_project_code(project_code)
        except ValueError as e:
            self.main_window.message_area.append(f"Error normalizing project code: {e}")
            return

        # Set directory path
        report_directory = config.REPORT_DIRECTORY
        year_directory = os.path.join(report_directory, f"Jobs 20{year_suffix}")

        # Check the directories exist
        if not os.path.isdir(year_directory):
            self.main_window.message_area.append(f"Year directory does not exist: {year_directory}")
            return

        # Search for the job in the year directory
        job_dir = None
        for dir_name in os.listdir(year_directory):
            dir_path = os.path.join(year_directory, dir_name)
            if not os.path.isdir(dir_path):
                continue

            # Normalize codes for comparison
            dir_code = dir_name[:6].strip()
            # Remove non-digit characters and leading zeros
            dir_code_digits = re.sub(r'\D', '', dir_code).lstrip('0')
            normalized_code_digits = re.sub(r'\D', '', normalized_code).lstrip('0')

            if dir_code_digits == normalized_code_digits:
                job_dir = dir_path
                break

        if not job_dir:
            self.main_window.message_area.append(f"Job directory not found for project code: {normalized_code} in {year_directory}")
            return

        # Confirm the correct directory
        confirm = QMessageBox.question(
            self.main_window,
            "Confirm Directory",
            f"Found job directory:\n\n{job_dir}\n\nIs this correct?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if confirm == QMessageBox.No:
            self.main_window.message_area.append("Job directory confirmation failed.")
            return

        # Check for Project_Reports directory
        reports_dir = os.path.join(job_dir, "Project_Reports")
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)

        # Construct the file name
        project_name = project.name
        stripped_project_name = project_name.replace('/', ' ')
        file_name = f"{normalized_code} {stripped_project_name}.xlsx"

        # Full path to save the workbook
        full_path = os.path.join(reports_dir, file_name)

        # Save the workbook
        save_result = save_workbook(report_workbook, full_path)

        if save_result:
            self.main_window.message_area.append(f"Report Created and saved at {full_path}")
        else:
            self.main_window.message_area.append("Failed to save workbook")

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
