import openpyxl
import datetime
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font

def create_workbook():
    # Create a new Excel workbook and active worksheet
    workbook = openpyxl.Workbook()
    sheet = workbook.active

    # Define column headers
    headers = [
        "Project ID", "Project Name", "Street 1", "Street 2", "City",
        "State", "Zip", "Project PO#", "Client ID", "Client Street 1",
        "Street 2", "City", "State", "Zip", "Billing Contact"
    ]

    # Insert headers into the first row
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=col, value=header)
    
    sheet['A4'] = "AHJ Jurisdiction"
    sheet['B4'] = "Building Code"
    sheet["C4"] = "Ammendments"

    return workbook

def insert_project_data(sheet, project):
    # Insert project data into the designated cells
    sheet['A2'] = project.code
    sheet['B2'] = project.name
    sheet['C2'] = project.street1
    sheet['D2'] = project.street2
    sheet['E2'] = project.city
    sheet['F2'] = project.state
    sheet['G2'] = project.zip_code
    sheet['H2'] = project.purchase_order_number

def insert_client_data(sheet, client):
    # Insert client data into the designated cells
    sheet['I2'] = client.client_id
    sheet['J2'] = client.street1
    sheet['K2'] = client.street2
    sheet['L2'] = client.city
    sheet['M2'] = client.state
    sheet['N2'] = client.zip_code
    sheet['O2'] = client.name  # Assuming 'Billing Contact' refers to client name


def auto_adjust_column_width(sheet):
    """
    Auto adjusts the column width to fit the content in each column.
    Args:
        sheet: The active sheet of the workbook.
    """
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


def insert_ahj_data(sheet, ahj_info, amendment_data):
    """
    Inserts AHJ and amendment data starting from row 5.
    Args:
        sheet: The active sheet of the workbook.
        ahj_info: A list of dictionaries containing AHJ data with keys 'AHJ Name' and 'Building Code'.
        amendments: A list of amendment URLs corresponding to AHJ names.
    """
    row_start = 5
    max_length = max(len(ahj_info), len(amendment_data)) # use which ever length is longer
    
    for i in range(max_length):
        ahj_name = ahj_info[i]['AHJ Name'] if i < len(ahj_info) else ''
        building_code = ahj_info[i]['Building Code'] if i < len(ahj_info) else ''
        amendment_url = amendment_data[i] if i < len(amendment_data) else ''
        
        sheet[f'A{row_start + i}'] = ahj_name
        sheet[f'B{row_start + i}'] = building_code
        
        if amendment_url:
            amendment_name = amendment_url.split('/')[-1]
            
            # Insert hyperlink for the amendment
            sheet.cell(row=row_start + i, column=3).hyperlink = amendment_url
            sheet.cell(row=row_start + i, column=3).value = amendment_name
            sheet.cell(row=row_start + i, column=3).font = Font(color="0000FF", underline="single")  # Make it look like a hyperlink

def save_workbook(workbook, full_path):
    """
    Saves the workbook to the specified full path.

    Args:
        workbook: The openpyxl workbook object.
        full_path: The full file path where the workbook should be saved.
    """
    try:
        sheet = workbook.active
        
        auto_adjust_column_width(sheet)
        
        workbook.save(full_path)
        
        return full_path
    except Exception as e:
        print(f"Failed to save workbook: {e}")
        return None

