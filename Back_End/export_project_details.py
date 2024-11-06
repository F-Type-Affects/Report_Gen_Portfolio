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
        "Project ID", "Project Name", "Project PO #", "Project Address", "Client",
        "Client Address", "Billing Contact", "AHJ Jurisdiction", "Amendment PDF Links", "Amendment Web Links",
        "Street 1", "Street 2", "City", "State", "Zip", "Phone", "Email"
    ]

    # Insert headers into the first row
    for col, header in enumerate(headers, start=1):
        sheet.cell(row=1, column=col, value=header)
    
    sheet['A1'] = "Project ID:"
    sheet['A2'] = "Project Name:"
    sheet['A3'] = "Project PO #:"
    sheet['A4'] = "Project Address:"
    sheet['A6'] = "Client:"
    sheet['A7'] = "Client Address:"
    sheet['A9'] = "Billing Contact:"
    sheet['A10'] = "Phone:"
    sheet['A11'] = "Email:"
    sheet['B4'] = "Street 1"
    sheet['C4'] = "Street 2"
    sheet['D4'] = "City"
    sheet['E4'] = "State"
    sheet['F4'] = "Zip"
    sheet['B7'] = "Street 1"
    sheet['C7'] = "Street 2"
    sheet['D7'] = "City"
    sheet['E7'] = "State"
    sheet['F7'] = "Zip"
    sheet['H1'] = "AHJ Jurisdiction:"
    sheet['H6'] = "Amendment PDF Links:"
    sheet['H17'] = "Amendment Web Links:"
    
    return workbook

def insert_project_data(sheet, project):
    # Insert project data into the designated cells
    sheet['B1'] = project.code
    sheet['B2'] = project.name
    sheet['B3'] = project.purchaseOrderNumber
    sheet['B5'] = project.street1
    sheet['C5'] = project.street2
    sheet['D5'] = project.city
    sheet['E5'] = project.state
    sheet['F5'] = project.zip_code

def insert_client_data(sheet, client):
    # Insert client data into the designated cells
    sheet['B6'] = client.name
    sheet['B8'] = client.street1
    sheet['C8'] = client.street2
    sheet['D8'] = client.city
    sheet['E8'] = client.state
    sheet['F8'] = client.zip_code
    sheet['B10'] = client.phone
    sheet['B11'] = client.email
    

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

