import openpyxl
import datetime
import openpyxl
import os
import logging
from .config import get_config
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill

config = get_config()

logger = logging.getLogger(__name__)

# Base directory for Jobs & Pools
BASE_DIR = config.REPORT_DIRECTORY
POOL_DIR = config.POOL_DIRECTORY

def create_workbook():
    # Create a new Excel workbook and active worksheet
    logger.info("Creating a new workbook with predefined headers.")
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    # Define and insert headers directly into specified cells
    headers = {
        'A1': "Project ID:", 'A2': "Project Name:", 'A3': "Project PO #:", 'A4': "Project Address:",
        'A6': "Client:", 'A7': "Client Address:", 'A9': "Billing Contact:", 'A10': "Phone:", 'A11': "Email:",
        'B4': "Street 1", 'C4': "Street 2", 'D4': "City", 'E4': "State", 'F4': "Zip",
        'B7': "Street 1", 'C7': "Street 2", 'D7': "City", 'E7': "State", 'F7': "Zip",
        'H1': "AHJ Jurisdiction:", 'I1': "AHJ Building Codes:", 'J1': "Amendment PDF Links:", 'K1': "Amendment Web Links:"
    }

    for cell, header in headers.items():
        sheet[cell] = header
        # Set header cells to bold with background color
        sheet[cell].font = Font(bold=True)
        sheet[cell].fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")  # Light grey fill

    logger.debug("Workbook headers added successfully.")
    return workbook


def insert_project_data(sheet, project):
    # Insert project data into the designated cells
    sheet['B1'] = project.get('code', '')  # Use get method to safely access keys
    sheet['B2'] = project.get('name', '')
    sheet['B3'] = project.get('purchase_order_number', '')
    sheet['B5'] = project.get('street1', '')
    sheet['C5'] = project.get('street2', '')
    sheet['D5'] = project.get('city', '')
    sheet['E5'] = project.get('state', '')
    sheet['F5'] = project.get('zip_code', '')
    
    logger.debug("Project data inserted successfully.")


def insert_client_data(sheet, client):
    # Insert client data into the designated cells
    sheet['B6'] = client.get('client_name', '')
    sheet['B8'] = client.get('street1', '')
    sheet['C8'] = client.get('street2', '')
    sheet['D8'] = client.get('city', '')
    sheet['E8'] = client.get('state', '')
    sheet['F8'] = client.get('zip_code', '')
    sheet['B10'] = client.get('client_phone', '')
    sheet['B11'] = client.get('client_email', '')
    
    logger.debug("Client data inserted successfully.")

    

def auto_adjust_column_width(sheet):
    """
    Auto adjusts the column width to fit the content in each column.
    Args:
        sheet: The active sheet of the workbook.
    """
    logger.info("Auto-adjusting column widths.")
    for col in sheet.columns:
        max_length = 0
        col_letter = get_column_letter(col[0].column)  # Get the letter of the column
        for cell in col:
            try:
                if cell.value:
                    # Calculate the length of the cell value (convert it to string first)
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        # Adjust the column width
        adjusted_width = (max_length + 2)
        sheet.column_dimensions[col_letter].width = adjusted_width
        
    logger.debug("Column widths adjusted.")

def insert_ahj_data(sheet, ahj_info, amendment_data):
    """
    Inserts AHJ and amendment data into columns H, I, J, and K starting from row 2.
    Args:
        sheet: The active sheet of the workbook.
        ahj_info: A list of dictionaries containing AHJ data.
        amendment_data: A dictionary with lists for 'pdf_links' and 'web_links' keys.
    """
    # Insert AHJ jurisdiction and building codes in columns H and I
    logger.info("Inserting AHJ and amendment data.")
    for row, ahj in enumerate(ahj_info, start=2):
        sheet[f'H{row}'] = ahj.get('AHJ Name', '')
        sheet[f'I{row}'] = ahj.get('Building Code', '')

    # Insert Amendment PDF Links in column J
    for row, pdf_link in enumerate(amendment_data.get('pdf_links', []), start=2):
        pdf_name = pdf_link.split('/')[-1]
        cell = sheet.cell(row=row, column=10)  # Column J is the 10th column
        cell.hyperlink = pdf_link
        cell.value = pdf_name
        cell.font = Font(color="0000FF", underline="single")  # Blue font to mimic a hyperlink

    # Insert Amendment Web Links in column K
    for row, web_link in enumerate(amendment_data.get('web_links', []), start=2):
        web_name = web_link.split('/')[-1]
        cell = sheet.cell(row=row, column=11)  # Column K is the 11th column
        cell.hyperlink = web_link
        cell.value = web_name
        cell.font = Font(color="0000FF", underline="single")  # Blue font to mimic a hyperlink
    
    logger.debug("AHJ and amendment data inserted successfully.")


def save_workbook(workbook, project_code):
    """
    Saves the workbook to the appropriate directory based on project code.

    Args:
        workbook (Workbook): The openpyxl workbook object.
        project_code (str): Project code to determine the save path.

    Returns:
        str: The full path of the saved workbook, or None if save failed.
    """
    # Find the project directory based on the project code
    logger.info(f"Saving workbook for project: {project_code}")
    project_dir = find_project_directory(project_code)
    
    if not project_dir:
        logger.error(f"Project directory not found for project code: {project_code}")
        return None

    # Define the AHJ_REPORT directory within the project folder
    ahj_report_dir = os.path.join(project_dir, "AHJ_REPORT")
    if not os.path.exists(ahj_report_dir):
        os.makedirs(ahj_report_dir)  # Create the directory if it doesn't exist
        logger.debug(f"Created directory: {ahj_report_dir}")

    # Create the filename with timestamp
    filename = f"AHJ_Report.xlsx"
    full_path = os.path.join(ahj_report_dir, filename)

    # Save the workbook
    try:
        workbook.save(full_path)
        logger.info(f"Workbook saved successfully at {full_path}")
        return full_path
    except Exception as e:
        logger.error(f"Failed to save workbook: {e}")
        return None

def find_project_directory(project_code):
    """
    Finds project directory for both General and Pool projects.
    
    Args:
        project_code (str): Project code in formats:
            General: "yy-xxxx" or "xxxx-yy"
            Pool: "yy-Pxxx"
            
    Returns:
        str: Path to project directory if found, None otherwise
    """
    logger.info(f"Finding project directory for project code: {project_code}")
    
    # Check if this is a pool project
    is_pool = 'P' in project_code.upper()
    
    try:
        if is_pool:
            if len(project_code) < 6 or project_code[2] != '-':
                logger.error(f"Invalid pool project code format: {project_code}")
                return None
                
            year = project_code[:2]
            code = project_code[4:].lstrip('0')  # Remove leading zeros
            year_full = "20" + year
            
            # Use POOL_DIR for pool projects
            year_folder = f"Pools-{year_full}"
            year_directory = os.path.join(POOL_DIR, year_folder)
            
            # Pool project folder prefix format
            project_folder_prefix = f"{code}-{year}P"
            
        else:
            # General project logic
            if len(project_code) == 7 and project_code[2] == '-':
                year, code = project_code[:2], project_code[3:]
                year_full = "20" + year
            elif len(project_code) == 7 and project_code[4] == '-':
                code, year = project_code[:4], project_code[5:]
                year_full = "20" + year
            else:
                logger.error(f"Invalid project code format: {project_code}")
                return None

            if len(code) == 4 and code.startswith('0'):
                code_formatted = code[1:]
            elif len(code) <= 3:
                code_formatted = code.zfill(3)
            else:
                code_formatted = code

            # Use BASE_DIR for general projects
            year_folder = f"Jobs {year_full}"
            year_directory = os.path.join(BASE_DIR, year_folder)
            project_folder_prefix = f"{code_formatted}-{year}"

        if not os.path.exists(year_directory):
            logger.warning(f"Year folder not found: {year_directory}")
            return None

        # Search for matching project directory
        for dir_name in os.listdir(year_directory):
            if dir_name.startswith(project_folder_prefix):
                project_directory = os.path.join(year_directory, dir_name)
                logger.info(f"Found project directory: {project_directory}")
                return project_directory

        logger.warning(f"Project directory not found for code: {project_code}")
        return None

    except Exception as e:
        logger.error(f"Error accessing project directory: {e}")
        return None