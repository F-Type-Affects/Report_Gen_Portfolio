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

#Directories to save cover letters to:
general_projects = config.COVER_LETTER_OUTPUT_DIR
pool_projects = config.COVER_LETTER_POOLS_OUTPUT

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
        template_path = config.COVER_LETTER_TEMPLATE_PATH
        logger.info(f"Template path: {template_path}")
        if not os.path.exists(template_path):
            logger.error(f"Template not found at {template_path}")
            return False

        doc = Document(template_path)
        replacements = {
            'Project': project_data['name'],
            'Location': f"{project_data['street1']} {project_data['street2']}, {project_data['city']}, {project_data['state']} {project_data['zip_code']}",
            'ClientName': client_data['client_name'],
            'JobNumber': project_data['code'],
            'By': f"{first_name} {last_name}"
        }

        for tag, value in replacements.items():
            replace_content_control_text(doc, tag, value)

        project_code = project_data['code']
        logger.info(f"Looking for project directory with code: {project_code}")
        project_directory = find_project_directory_letter(project_code)
        logger.info(f"Found project directory: {project_directory}")
        
        if not project_directory:
            logger.error(f"Project directory not found for code: {project_code}")
            return False

        is_pool = 'P' in project_code.upper()
        if is_pool:
            calculations_directory = os.path.join(project_directory, "Eng")
            logger.info(f"Pool project detected, using directory: {calculations_directory}")
        else:
            calculations_directory = os.path.join(project_directory, "ENG", "Calculations")
            logger.info(f"General project detected, using directory: {calculations_directory}")
            
        if not os.path.exists(calculations_directory):
            logger.error(f"Required directory does not exist: {calculations_directory}")
            return False

        output_filename = f"calc_cover_{project_code}.docx"
        output_path = os.path.join(calculations_directory, output_filename)
        logger.info(f"Attempting to save file at: {output_path}")

        doc.save(output_path)
        logger.info(f"File saved successfully at: {output_path}")
        logger.info(f"File exists after save: {os.path.exists(output_path)}")

        return True

    except Exception as e:
        logger.error(f"Error generating cover letter: {str(e)}")
        logger.exception("Full traceback:")
        return False


def find_project_directory_letter(project_code):
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
            year_directory = os.path.join(pool_projects, year_folder)
            
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
            year_directory = os.path.join(general_projects, year_folder)
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

