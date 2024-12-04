# cover_letter.py
import os
from shutil import copyfile
from docx import Document
import logging

logger = logging.getLogger(__name__)

def generate_cover_letter(project_data, client_data, first_name, last_name):
    """
    Generates the cover letter document based on the template and provided data.

    Args:
        project_data (dict): Project details.
        client_data (dict): Client details.
        first_name (str): User's first name.
        last_name (str): User's last name.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # Path to the template
        template_path = r"D:\Report_Cover_Page\Cover_Page_Template.docx"
        if not os.path.exists(template_path):
            logger.error(f"Template not found at {template_path}")
            return False

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

        # Copy the template to the output path
        copyfile(template_path, output_path)

        # Open the document
        doc = Document(output_path)

        # Replace placeholders in the document
        replacements = {
            '{P}': project_data['name'],
            '{L}': f"{project_data['street1']} {project_data['street2']}, {project_data['city']}, {project_data['state']} {project_data['zip_code']}",
            '{C}': client_data['client_name'],
            '{J}': project_data['code'],
            '{B}': f"{first_name} {last_name}"
        }

        for paragraph in doc.paragraphs:
            for key, value in replacements.items():
                if key in paragraph.text:
                    paragraph.text = paragraph.text.replace(key, value)

        # Save the modified document
        doc.save(output_path)

        return True

    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        return False

# cover_letter.py
def find_project_directory_letter(project_code):
    """
    Finds the project directory based on the project code format.

    Args:
        project_code (str): Project code in format "yy-code" or "code-yy".

    Returns:
        str: Path to the project directory if it exists, or None if not found.
    """
    logger.info(f"Finding project directory for project code: {project_code}")
    if len(project_code) == 7 and project_code[2] == '-':
        year, code = project_code[:2], project_code[3:]
        year_full = "20" + year
    elif len(project_code) == 8 and project_code[4] == '-':
        code, year = project_code[:4], project_code[5:]
        year_full = "20" + year
    else:
        logger.error("Invalid project code format.")
        return None

    base_dir = r"D:\Jobs"  # Adjust BASE_DIR to your actual base directory
    year_folder = f"Jobs {year_full}"
    project_folder_name = f"{int(code)}-{year}"

    year_directory = os.path.join(base_dir, year_folder)
    logger.debug(f"Constructed year folder path: {year_directory}")

    if not os.path.exists(year_directory):
        logger.warning(f"Year folder not found: {year_directory}")
        return None

    try:
        for dir_name in os.listdir(year_directory):
            if dir_name.startswith(project_folder_name):
                return os.path.join(year_directory, dir_name)
    except Exception as e:
        logger.error(f"Error accessing project directory: {e}")
        return None

    logger.warning(f"Project directory not found for project code: {project_code}")
    return None
