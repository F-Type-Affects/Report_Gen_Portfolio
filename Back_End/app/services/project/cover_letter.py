"""
Enhanced Cover Letter Generation Service for SML Templates
Supports SML-specific template requirements and data mapping
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime

from app.core.config import get_config
from app.services.project.coverletter_template_manager import template_manager, TemplateConfig

config = get_config()
logger = logging.getLogger(__name__)

# Define the 'w' namespace for Word processing
NAMESPACE = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
namespaces = {'w': NAMESPACE}

class SMLCoverLetterGenerator:
    """SML-specific cover letter generator supporting multiple templates"""
    
    def __init__(self):
        self.template_manager = template_manager
    
    def generate_cover_letter(
        self, 
        template_id: str,
        project_data: Dict[str, Any], 
        client_data: Dict[str, Any], 
        user_data: Dict[str, Any],
        engineer_initials: Optional[str] = None,
        pool_standard: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Generate cover letter using specified SML template
        
        Args:
            template_id: Template identifier
            project_data: Project information dictionary
            client_data: Client information dictionary  
            user_data: User information dictionary
            engineer_initials: Engineer initials for pool templates (PP/JK, MS/JK, or JK)
            pool_standard: Pool standard for specific pool templates (30 psf/ft, 45 psf/ft, or Custom)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate template
            template_config = self.template_manager.get_template_config(template_id)
            if not template_config:
                error_msg = f"Template not found: {template_id}"
                logger.error(error_msg)
                return False, error_msg
            
            if not self.template_manager.validate_template_exists(template_id):
                error_msg = f"Template file not found: {template_config.file_name}"
                logger.error(error_msg)
                return False, error_msg
            
            # Validate pool standard for templates requiring it
            if template_config.has_pool_standard:
                if not pool_standard:
                    error_msg = "Pool standard is required for this template"
                    logger.error(error_msg)
                    return False, error_msg
                
                if not self.template_manager.validate_pool_standard(pool_standard):
                    error_msg = f"Invalid pool standard: {pool_standard}"
                    logger.error(error_msg)
                    return False, error_msg
            
            # Validate engineer initials for pool templates
            if template_config.has_engineer_initials:
                if not engineer_initials:
                    error_msg = "Engineer initials are required for pool templates"
                    logger.error(error_msg)
                    return False, error_msg
                
                if not self.template_manager.validate_engineer_initials(engineer_initials):
                    error_msg = f"Invalid engineer initials: {engineer_initials}"
                    logger.error(error_msg)
                    return False, error_msg
            
            # Load template document
            template_path = template_config.get_template_path()
            logger.info(f"Loading template: {template_path}")
            
            if not os.path.exists(template_path):
                error_msg = f"Template file does not exist: {template_path}"
                logger.error(error_msg)
                return False, error_msg
            
            doc = Document(template_path)
            
            # Prepare replacement data based on template type
            replacement_data = self._prepare_sml_replacement_data(
                template_config, project_data, client_data, user_data, engineer_initials, pool_standard
            )
            
            # Validate required fields
            missing_fields = self._validate_required_fields(template_config, replacement_data)
            if missing_fields:
                error_msg = f"Missing required fields for template {template_id}: {missing_fields}"
                logger.error(error_msg)
                return False, error_msg
            
            # Apply replacements to document
            self._apply_replacements(doc, replacement_data)
            
            # Save document to project directory
            success, save_message = self._save_document(doc, project_data['code'], template_config)
            
            if success:
                logger.info(f"Cover letter generated successfully: {save_message}")
                return True, f"Cover letter generated successfully using {template_config.display_name} template"
            else:
                logger.error(f"Failed to save cover letter: {save_message}")
                return False, f"Failed to save cover letter: {save_message}"
                
        except Exception as e:
            error_msg = f"Error generating cover letter with template {template_id}: {str(e)}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            return False, error_msg
    
    def _prepare_sml_replacement_data(
        self,
        template_config: TemplateConfig,
        project_data: Dict[str, Any],
        client_data: Dict[str, Any],
        user_data: Dict[str, Any],
        engineer_initials: Optional[str] = None,
        pool_standard: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Prepare replacement data based on SML template requirements
        
        Args:
            template_config: Template configuration
            project_data: Project information
            client_data: Client information
            user_data: User information
            engineer_initials: Engineer initials for pool templates
            pool_standard: Pool standard for specific pool templates
            
        Returns:
            Dictionary of replacement key-value pairs
        """
        # Format location from project data
        location = self._format_project_location(project_data)
        
        # Format client information based on template requirements
        if template_config.client_format == "separate_fields":
            # Separate fields format: Name in Client, address in ClientAddress (used by all pool templates)
            client_info = client_data.get('client_name', '')
            client_address = self._format_client_address(client_data)
        else:
            # General template format: Name only (used by general_calc template)
            client_info = client_data.get('client_name', '')
            client_address = None
        
        # Base replacements for all SML templates
        replacements = {
            'Project': project_data.get('name', ''),
            'Location': location,
            'Client': client_info,
            'Date': datetime.now().strftime('%m/%d/%y'),  # Format: M/D/YY (e.g., 7/17/25)
            'JobNumber': project_data.get('code', ''),
        }
        
        # Add ClientAddress field for templates using separate fields
        if template_config.client_format == "separate_fields" and client_address is not None:
            replacements['ClientAddress'] = client_address
        
        # Handle different "By" field requirements
        if template_config.has_engineer_initials:
            # Pool templates use engineer initials
            replacements['By'] = engineer_initials or ''
        else:
            # General template uses full name
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            replacements['By'] = f"{first_name} {last_name}".strip()
        
        # Add "Checked By" for pool templates
        if template_config.has_checked_by:
            replacements['CheckedBy'] = 'J. Light, SE'
        
        # Add "Standard" for templates requiring pool standard
        if template_config.has_pool_standard:
            replacements['Standard'] = pool_standard or ''
        
        # Clean up empty values
        replacements = {k: v if v is not None else '' for k, v in replacements.items()}
        
        logger.debug(f"Prepared replacement data for template {template_config.template_id}: {list(replacements.keys())}")
        return replacements
    
    def _format_project_location(self, project_data: Dict[str, Any]) -> str:
        """Format project location from address components for SML requirements"""
        components = [
            project_data.get('street1', ''),
            project_data.get('street2', ''),
            project_data.get('city', ''),
            project_data.get('state', ''),
            project_data.get('zip_code', '')
        ]
        
        # Filter out empty components
        location_parts = [comp.strip() for comp in components if comp and comp.strip()]
        
        if len(location_parts) >= 3:
            # Format as: Street1 Street2, City, State ZIP
            street_parts = []
            if location_parts[0]:  # street1
                street_parts.append(location_parts[0])
            if len(location_parts) > 1 and location_parts[1]:  # street2
                street_parts.append(location_parts[1])
            
            street = ' '.join(street_parts)
            city_state_zip = ', '.join(location_parts[2:])  # city, state, zip
            
            return f"{street}, {city_state_zip}" if street else city_state_zip
        else:
            return ', '.join(location_parts)
    
    def _format_client_address(self, client_data: Dict[str, Any]) -> str:
        """Format client address for pool templates"""
        address_components = [
            client_data.get('street1', ''),
            client_data.get('street2', ''),
            client_data.get('city', ''),
            client_data.get('state', ''),
            client_data.get('zip_code', '')
        ]
        
        # Filter out empty components
        address_parts = [comp.strip() for comp in address_components if comp and comp.strip()]
        
        if len(address_parts) >= 3:
            # Format as: Street1 Street2, City, State ZIP
            street_parts = []
            if address_parts[0]:  # street1
                street_parts.append(address_parts[0])
            if len(address_parts) > 1 and address_parts[1]:  # street2
                street_parts.append(address_parts[1])
            
            street = ' '.join(street_parts)
            city_state_zip = ', '.join(address_parts[2:])  # city, state, zip
            
            return f"{street}, {city_state_zip}" if street else city_state_zip
        else:
            return ', '.join(address_parts)
    
    def _validate_required_fields(
        self, 
        template_config: TemplateConfig, 
        replacement_data: Dict[str, str]
    ) -> List[str]:
        """Validate that all required fields are present"""
        missing_fields = []
        
        for required_field in template_config.required_fields:
            if required_field not in replacement_data or not replacement_data[required_field].strip():
                missing_fields.append(required_field)
        
        return missing_fields
    
    def _apply_replacements(self, doc: Document, replacements: Dict[str, str]) -> None:
        """Apply all replacements to the document"""
        for tag, value in replacements.items():
            if value:  # Only replace if value is not empty
                self._replace_content_control_text(doc, tag, value)
    
    def _replace_content_control_text(self, doc: Document, tag: str, new_text: str) -> None:
        """
        Replace text in content control with proper formatting
        Enhanced version with better handling for multi-line text (client addresses)
        """
        try:
            # Iterate through all content controls (sdt elements)
            for sdt in doc.element.findall('.//w:sdt', namespaces):
                # Find the tag element within the content control
                tag_elem = sdt.find('.//w:tag', namespaces)
                if tag_elem is not None and tag_elem.get(qn('w:val')) == tag:
                    # Find the text element within the content control
                    text_elem = sdt.find('.//w:t', namespaces)
                    if text_elem is not None:
                        # Handle multi-line text (for client addresses in pool templates)
                        if '\n' in new_text:
                            self._replace_multiline_text(text_elem, new_text)
                        else:
                            # Replace single-line text
                            text_elem.text = new_text
                        
                        logger.debug(f"Replaced content control '{tag}' with '{new_text}'")
                        
                        # Apply appropriate formatting based on content control type
                        if tag == 'Standard':
                            self._apply_standard_formatting(text_elem)
                        else:
                            self._apply_general_formatting(text_elem)
                        break
            else:
                logger.warning(f"Content control with tag '{tag}' not found in document")
                
        except Exception as e:
            logger.error(f"Error replacing content control '{tag}': {e}")
    
    def _replace_multiline_text(self, text_elem, new_text: str) -> None:
        """Handle multi-line text replacement with proper Word line breaks"""
        try:
            lines = new_text.split('\n')
        
            # Set the first line in the original text element
            text_elem.text = lines[0]
        
            # Get the parent run
            run = text_elem.getparent()
        
            # Add subsequent lines with proper Word line breaks
            for line in lines[1:]:
                if line.strip():  # Only add non-empty lines
                    # Create a manual line break (w:br)
                    br = OxmlElement('w:br')
                    run.append(br)
                
                    # Create a new text element for this line
                    new_text_elem = OxmlElement('w:t')
                    new_text_elem.text = line
                    run.append(new_text_elem)
                
        except Exception as e:
            logger.error(f"Error handling multiline text: {e}")
            # Fallback: use comma separation
            text_elem.text = new_text.replace('\n', ', ')
    
    def _apply_standard_formatting(self, text_elem) -> None:
        """Apply formatting for Standard content control: Times New Roman, 16pt, Bold, Underlined"""
        try:
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
                
                # Set font size to 16pt (32 half-points)
                sz = rPr.find(qn('w:sz'))
                if sz is None:
                    sz = OxmlElement('w:sz')
                    rPr.append(sz)
                sz.set(qn('w:val'), '32')
                
                # Set font color to black
                color = rPr.find(qn('w:color'))
                if color is None:
                    color = OxmlElement('w:color')
                    rPr.append(color)
                color.set(qn('w:val'), '000000')
                
                # Add bold formatting
                b = rPr.find(qn('w:b'))
                if b is None:
                    b = OxmlElement('w:b')
                    rPr.append(b)
                b.set(qn('w:val'), 'true')
                
                # Add underline formatting
                u = rPr.find(qn('w:u'))
                if u is None:
                    u = OxmlElement('w:u')
                    rPr.append(u)
                u.set(qn('w:val'), 'single')
                
        except Exception as e:
            logger.error(f"Error applying standard formatting to content control: {e}")
    
    def _apply_general_formatting(self, text_elem) -> None:
        """Apply formatting for general content controls: Times New Roman, 14pt"""
        try:
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
                
                # Set font size to 14pt (28 half-points)
                sz = rPr.find(qn('w:sz'))
                if sz is None:
                    sz = OxmlElement('w:sz')
                    rPr.append(sz)
                sz.set(qn('w:val'), '28')
                
                # Set font color to black
                color = rPr.find(qn('w:color'))
                if color is None:
                    color = OxmlElement('w:color')
                    rPr.append(color)
                color.set(qn('w:val'), '000000')
                
        except Exception as e:
            logger.error(f"Error applying general formatting to content control: {e}")
    
    def _save_document(
        self, 
        doc: Document, 
        project_code: str, 
        template_config: TemplateConfig
    ) -> Tuple[bool, str]:
        """Save document to appropriate project directory with SML naming convention"""
        try:
            # Find project directory (reuse existing logic from original cover_letter.py)
            project_directory = self._find_project_directory_letter(project_code)
            
            if not project_directory:
                return False, f"Project directory not found for code: {project_code}"
            
            # Determine save directory based on project type
            is_pool = 'P' in project_code.upper()
            if is_pool:
                calculations_directory = os.path.join(project_directory, "Eng")
            else:
                calculations_directory = os.path.join(project_directory, "ENG", "Calculations")
            
            if not os.path.exists(calculations_directory):
                return False, f"Calculations directory does not exist: {calculations_directory}"
            
            # Create filename with SML naming convention
            if template_config.has_engineer_initials:
                # Pool template: calc_cover_ProjectCode_TemplateType.docx
                template_suffix = template_config.template_type.value.replace('pool_', '').replace('_', '')
                output_filename = f"calc_cover_{project_code}_{template_suffix}.docx"
            else:
                # General template: calc_cover_ProjectCode.docx
                output_filename = f"calc_cover_{project_code}.docx"
            
            output_path = os.path.join(calculations_directory, output_filename)
            
            # Save document
            doc.save(output_path)
            
            if os.path.exists(output_path):
                logger.info(f"Document saved successfully: {output_path}")
                return True, output_path
            else:
                return False, "File was not created successfully"
                
        except Exception as e:
            error_msg = f"Error saving document: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def _find_project_directory_letter(self, project_code: str) -> Optional[str]:
        """
        Find project directory - reused from original implementation
        This maintains compatibility with existing directory structure
        """
        logger.info(f"Finding project directory for project code: {project_code}")
        
        # Check if this is a pool project
        is_pool = 'P' in project_code.upper()
        
        try:
            general_projects = config.COVER_LETTER_OUTPUT_DIR
            pool_projects = config.COVER_LETTER_POOLS_OUTPUT
            
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

# Global instance
sml_cover_letter_generator = SMLCoverLetterGenerator()