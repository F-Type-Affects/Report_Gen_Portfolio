import openpyxl
import datetime
import openpyxl
import os
import logging
from .config import get_config
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill
from .models import ASCESummaryData
from typing import Tuple

config = get_config()

logger = logging.getLogger(__name__)

# Base directory for Jobs
BASE_DIR = config.REPORT_DIRECTORY

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

    # Auto-adjust column widths before saving
    auto_adjust_column_width(workbook.active)

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
            
            # Updated pool paths to use root Pools directory
            pools_dir = os.path.join('J:', 'Pools')
            year_folder = f"Pools-{year_full}"
            year_directory = os.path.join(pools_dir, year_folder)
            
            # Updated pool project folder prefix format
            project_folder_prefix = f"{code}-{year}P"
            
        else:
            # Existing general project logic remains unchanged
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

            base_dir = config.COVER_LETTER_OUTPUT_DIR
            year_folder = f"Jobs {year_full}"
            year_directory = os.path.join(base_dir, year_folder)
            project_folder_prefix = f"{code_formatted}-{year}"

        if not os.path.exists(year_directory):
            logger.warning(f"Year folder not found: {year_directory}")
            return None

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
    
def find_report_workbook(project_code):
    """
    Finds the AHJ Report workbook for a given project code.
    
    Args:
        project_code (str): Project code in formats:
            General: "yy-xxxx" or "xxxx-yy"
            Pool: "yy-Pxxx"
            
    Returns:
        tuple: (bool, str) where:
            - bool indicates if workbook was found
            - str contains either the full path to the workbook or an error message
    """
    logger.info(f"Searching for AHJ Report workbook for project: {project_code}")
    
    try:
        # Use existing function to find the project directory
        project_dir = find_project_directory(project_code)
        
        if not project_dir:
            logger.error(f"Project directory not found for project code: {project_code}")
            return False, "Project directory not found"

        # Look for AHJ_REPORT subdirectory
        ahj_report_dir = os.path.join(project_dir, "AHJ_REPORT")
        if not os.path.exists(ahj_report_dir):
            logger.error(f"AHJ_REPORT directory not found in project folder: {project_dir}")
            return False, "AHJ_REPORT directory not found"

        # Look for the workbook file
        workbook_path = os.path.join(ahj_report_dir, "AHJ_Report.xlsx")
        if not os.path.exists(workbook_path):
            logger.error(f"AHJ_Report.xlsx not found in: {ahj_report_dir}")
            return False, "AHJ_Report.xlsx not found"

        logger.info(f"AHJ Report workbook found at: {workbook_path}")
        return True, workbook_path

    except Exception as e:
        error_msg = f"Error while searching for AHJ Report workbook: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def insert_summary_sheet(workbook: openpyxl.Workbook, summary_data: ASCESummaryData) -> None:
    """
    Inserts ASCE summary data as a new worksheet in an existing workbook.
    
    Args:
        workbook: Existing openpyxl Workbook object
        summary_data: ASCESummaryData object containing the scraped data
    """
    logger.info("Creating ASCE Summary worksheet")
    
    # Create new worksheet
    sheet = workbook.create_sheet("ASCE Summary")
    
    # Set up headers with styling
    headers = ['Section', 'Parameter', 'Value', 'Unit']
    for col, header in enumerate(headers, 1):
        cell = sheet.cell(row=1, column=col)
        cell.value = header
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    
    current_row = 2
    
    # Wind Section
    sheet.cell(row=current_row, column=1, value="Wind")
    current_row += 1
    
    wind_params = [
        ("Wind Speed", summary_data.wind_data.wind_speed, "Vmph"),
        ("10-year MRI", summary_data.wind_data.ten_year_mri, "Vmph"),
        ("25-year MRI", summary_data.wind_data.twenty_five_year_mri, "Vmph"),
        ("50-year MRI", summary_data.wind_data.fifty_year_mri, "Vmph"),
        ("100-year MRI", summary_data.wind_data.hundred_year_mri, "Vmph")
    ]
    
    for param, value, unit in wind_params:
        sheet.cell(row=current_row, column=2, value=param)
        sheet.cell(row=current_row, column=3, value=value)
        sheet.cell(row=current_row, column=4, value=unit)
        current_row += 1
    
    # Seismic Section
    current_row += 1
    sheet.cell(row=current_row, column=1, value="Seismic")
    current_row += 1
    
    seismic_params = [
        ("SS", summary_data.seismic_data.SS, ""),
        ("S1", summary_data.seismic_data.S1, ""),
        ("Fa", summary_data.seismic_data.Fa, ""),
        ("Fv", summary_data.seismic_data.Fv, ""),
        ("SMS", summary_data.seismic_data.SMS, ""),
        ("SM1", summary_data.seismic_data.SM1, ""),
        ("SDS", summary_data.seismic_data.SDS, ""),
        ("SD1", summary_data.seismic_data.SD1, ""),
        ("TL", summary_data.seismic_data.TL, ""),
        ("PGA", summary_data.seismic_data.PGA, ""),
        ("PGAM", summary_data.seismic_data.PGAM, ""),
        ("FPGA", summary_data.seismic_data.FPGA, ""),
        ("Ie", summary_data.seismic_data.Ie, ""),
        ("Cv", summary_data.seismic_data.Cv, ""),
        ("Seismic Design Category", summary_data.seismic_data.seismic_design_category, ""),
        ("No Seismic Spectrum", summary_data.seismic_data.no_seismic_spectrum, ""),
        ("Spectrum Note", summary_data.seismic_data.spectrum_note, "")
    ]
    
    for param, value, unit in seismic_params:
        sheet.cell(row=current_row, column=2, value=param)
        sheet.cell(row=current_row, column=3, value=value if value is not None else "N/A")
        sheet.cell(row=current_row, column=4, value=unit)
        current_row += 1
    
    # Ice Section
    current_row += 1
    sheet.cell(row=current_row, column=1, value="Ice")
    current_row += 1
    
    ice_params = [
        ("Thickness", summary_data.ice_data.thickness, "in."),
        ("Concurrent Temperature", summary_data.ice_data.concurrent_temperature, "F"),
        ("Gust Speed", summary_data.ice_data.gust_speed, "mph")
    ]
    
    for param, value, unit in ice_params:
        sheet.cell(row=current_row, column=2, value=param)
        sheet.cell(row=current_row, column=3, value=value)
        sheet.cell(row=current_row, column=4, value=unit)
        current_row += 1
    
    # Snow Section
    current_row += 1
    sheet.cell(row=current_row, column=1, value="Snow")
    current_row += 1
    
    snow_params = [
        ("Ground Snow Load, pg", summary_data.snow_data.ground_snow_load_pg, "lb/ft2"),
        ("Ground Snow Load, pg (2400.0 ft)", summary_data.snow_data.ground_snow_load_pg_elevation, "lb/ft2"),
        ("Mapped Elevation", summary_data.snow_data.mapped_elevation, "ft")
    ]
    
    for param, value, unit in snow_params:
        sheet.cell(row=current_row, column=2, value=param)
        sheet.cell(row=current_row, column=3, value=value)
        sheet.cell(row=current_row, column=4, value=unit)
        current_row += 1
    
    # Adjust column widths
    auto_adjust_column_width(sheet)
    
    logger.info("ASCE Summary worksheet created successfully")

def update_workbook_with_summary(project_code: str, summary_data: ASCESummaryData) -> Tuple[bool, str]:
    """
    Updates the AHJ Report workbook with ASCE summary data.
    
    Args:
        project_code: Project code to locate the workbook
        summary_data: ASCESummaryData object containing the scraped data
        
    Returns:
        Tuple[bool, str]: Success status and message/path
    """
    logger.info(f"Attempting to update workbook with ASCE summary for project: {project_code}")
    
    try:
        # First find the workbook
        success, result = find_report_workbook(project_code)
        if not success:
            logger.error(f"Could not find workbook: {result}")
            return False, result
            
        workbook_path = result
        
        # Load the workbook
        try:
            workbook = openpyxl.load_workbook(workbook_path)
        except Exception as e:
            error_msg = f"Error loading workbook: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
        # Remove existing ASCE Summary sheet if it exists
        if "ASCE Summary" in workbook.sheetnames:
            del workbook["ASCE Summary"]
            
        # Insert new summary sheet
        insert_summary_sheet(workbook, summary_data)
        
        # Save the workbook
        try:
            workbook.save(workbook_path)
            logger.info(f"Workbook updated successfully at: {workbook_path}")
            return True, workbook_path
        except Exception as e:
            error_msg = f"Error saving workbook: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Unexpected error updating workbook: {str(e)}"
        logger.error(error_msg)
        return False, error_msg