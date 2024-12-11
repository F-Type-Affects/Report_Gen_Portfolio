import os
from shutil import copyfile
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import logging
from .config import get_config

config = get_config()

logger = logging.getLogger(__name__)

# Define the 'w' namespace
NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
namespaces = {'w': NAMESPACE}

def replace_content_control_text(doc, tag, new_text):
    """
    Replace the text inside a content control with the given tag and apply formatting.

    :param doc: The Document object
    :param tag: The tag of the content control to replace
    :param new_text: The new text to insert
    """
    # Iterate through all content controls (sdt elements)
    for sdt in doc.element.findall('.//w:sdt', namespaces):
        # Find the tag element within the content control
        tag_elem = sdt.find('.//w:tag', namespaces)
        if tag_elem is not None and tag_elem.get(qn('w:val')) == tag:
            # Find the text element within the content control
            text_elem = sdt.find('.//w:t', namespaces)
            if text_elem is not None:
                # Replace the text
                text_elem.text = new_text
                logger.info(f"Replaced content control '{tag}' with '{new_text}'")
                
                # Find the run (w:r) parent of the text element
                r = text_elem.getparent()
                while r is not None and r.tag != qn('w:r'):
                    r = r.getparent()
                
                if r is not None:
                    # Find or create run properties (w:rPr)
                    rPr = r.find(qn('w:rPr'))
                    if rPr is None:
                        rPr = OxmlElement('w:rPr')
                        r.insert(0, rPr)
                    
                    # Set font to Times New Roman
                    rFonts = rPr.find(qn('w:rFonts'))
                    if rFonts is None:
                        rFonts = OxmlElement('w:rFonts')
                        rPr.append(rFonts)
                    rFonts.set(qn('w:ascii'), 'Times New Roman')
                    rFonts.set(qn('w:hAnsi'), 'Times New Roman')
                    rFonts.set(qn('w:cs'), 'Times New Roman')
                    
                    # Set font size to 12 (value is in half-points, so 24 represents 12pt)
                    sz = rPr.find(qn('w:sz'))
                    if sz is None:
                        sz = OxmlElement('w:sz')
                        rPr.append(sz)
                    sz.set(qn('w:val'), '24')  # 24 half-points = 12 points
                    
                    # Set font color to black
                    color = rPr.find(qn('w:color'))
                    if color is None:
                        color = OxmlElement('w:color')
                        rPr.append(color)
                    color.set(qn('w:val'), '000000')  # Black color

    return doc

def generate_cover_letter(project_data, client_data, first_name, last_name):
    try:
        # Path to the template
        template_path = config.COVER_LETTER_TEMPLATE_PATH
        if not os.path.exists(template_path):
            logger.error(f"Template not found at {template_path}")
            return False

        # Open the template
        doc = Document(template_path)
        logger.info(f"Opened template at {template_path}")

        # Define replacements using content control tags
        replacements = {
            'Project': project_data['name'],
            'Location': f"{project_data['street1']} {project_data['street2']}, {project_data['city']}, {project_data['state']} {project_data['zip_code']}",
            'ClientName': client_data['client_name'],
            'JobNumber': project_data['code'],
            'By': f"{first_name} {last_name}"
        }

        # Replace text in content controls
        for tag, value in replacements.items():
            replace_content_control_text(doc, tag, value)

        # Find the project directory
        project_code = project_data['code']
        project_directory = find_project_directory_letter(project_code)
        if not project_directory:
            logger.error(f"Project directory not found for project code: {project_code}")
            return False

        # Construct the path to the Calculations directory
        calculations_directory = os.path.join(project_directory, "ENG", "Calculations")
        os.makedirs(calculations_directory, exist_ok=True)

        # Path to save the new cover letter
        output_filename = f"calc_cover_{project_code}.docx"
        output_path = os.path.join(calculations_directory, output_filename)

        # Save the modified document
        doc.save(output_path)
        logger.info(f"Cover letter generated at {output_path}")

        return True

    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        return False


def find_project_directory_letter(project_code):
    """
    Finds the project directory based on the project code format.

    Args:
        project_code (str): Project code in format "yy-xxxx" or "xxxx-yy".

    Returns:
        str: Path to the project directory if it exists, or None if not found.
    """
    logger.info(f"Finding project directory for project code: {project_code}")

    # Handle "yy-xxxx" format (e.g., "24-0022")
    if len(project_code) == 7 and project_code[2] == '-':
        year, code = project_code[:2], project_code[3:]
        year_full = "20" + year
        logger.debug(f"Parsed format 'yy-xxxx': year={year_full}, code={code}")

    # Handle "xxxx-yy" format (e.g., "0022-23")
    elif len(project_code) == 7 and project_code[4] == '-':
        code, year = project_code[:4], project_code[5:]
        year_full = "20" + year
        logger.debug(f"Parsed format 'xxxx-yy': year={year_full}, code={code}")

    else:
        logger.error(f"Invalid project code format: {project_code}")
        return None

    # Format the project code to match directory naming
    if len(code) == 4 and code.startswith('0'):
        # Remove the leading zero for codes like "0022" -> "022"
        code_formatted = code[1:]
        logger.debug(f"Formatted 4-digit code with leading zero: {code} -> {code_formatted}")
    elif len(code) <= 3:
        # Ensure 3-digit format with leading zeros if necessary
        code_formatted = code.zfill(3)
        logger.debug(f"Formatted code to 3 digits: {code} -> {code_formatted}")
    else:
        # Keep the code as is for 4-digit codes without leading zeros
        code_formatted = code
        logger.debug(f"Formatted code (no changes needed): {code} -> {code_formatted}")

    # Construct the project folder name
    project_folder_name = f"{code_formatted}-{year}"
    logger.debug(f"Constructed project folder name: {project_folder_name}")

    # Construct the full path to the year directory
    base_dir = config.COVER_LETTER_OUTPUT_DIR
    year_folder = f"Jobs {year_full}"
    year_directory = os.path.join(base_dir, year_folder)
    logger.debug(f"Constructed year folder path: {year_directory}")

    # Check if the year directory exists
    if not os.path.exists(year_directory):
        logger.warning(f"Year folder not found: {year_directory}")
        return None

    # Search for the project directory within the year directory
    try:
        for dir_name in os.listdir(year_directory):
            if dir_name.startswith(project_folder_name):
                project_directory = os.path.join(year_directory, dir_name)
                logger.info(f"Found project directory: {project_directory}")
                return project_directory
    except Exception as e:
        logger.error(f"Error accessing project directory: {e}")
        return None

    # If the project directory is not found
    logger.warning(f"Project directory not found for project code: {project_code}")
    return None

