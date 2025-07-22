# app/services/project/template_manager.py
"""
Template Management System for Cover Letters
Handles SML-specific template types and their data requirements
"""

import os
import json
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from app.core.config import get_config

config = get_config()
logger = logging.getLogger(__name__)

class TemplateType(Enum):
    """Enumeration of SML template types"""
    GENERAL_CALCULATIONS = "general_calculations"
    POOL_STANDARD = "pool_standard"
    POOL_REVISION = "pool_revision"
    POOL_SHASTA_SUPPLEMENTAL = "pool_shasta_supplemental"
    POOL_SK_SUPPLEMENTAL = "pool_sk_supplemental"
    POOL_SOILS_REPORT = "pool_soils_report"
    POOL_SHASTA_STANDARD = "pool_shasta_standard"
    POOL_SHASTA_COMMERCIAL = "pool_shasta_commercial"

@dataclass
class TemplateConfig:
    """Configuration for individual template"""
    template_id: str
    display_name: str
    file_name: str
    template_type: TemplateType
    required_fields: List[str]
    optional_fields: List[str]
    description: str
    has_engineer_initials: bool = False  # Special flag for pool templates
    has_checked_by: bool = False  # Special flag for pool templates
    has_pool_standard: bool = False  # Special flag for templates requiring pool standard selection
    client_format: str = "name_only"  # "name_only" or "name_with_address"
    is_active: bool = True
    
    def get_template_path(self) -> str:
        """Get full path to template file"""
        templates_dir = getattr(config, 'COVER_LETTER_TEMPLATES_DIR', 
                               os.path.join(os.path.dirname(__file__), '..', '..', '..', 'templates', 'cover_letters'))
        return os.path.join(templates_dir, self.file_name)

class EngineerInitials:
    """Available engineer initial combinations for pool templates"""
    OPTIONS = [
        {"value": "PP/JK", "display": "PP/JK"},
        {"value": "MS/JK", "display": "MS/JK"}, 
        {"value": "JK", "display": "JK"}
    ]
    
    @classmethod
    def get_options(cls) -> List[Dict[str, str]]:
        """Get available engineer initial options"""
        return cls.OPTIONS
    
    @classmethod
    def is_valid(cls, initials: str) -> bool:
        """Validate engineer initials"""
        return initials in [option["value"] for option in cls.OPTIONS]

class PoolStandardOption:
    """Available pool standard options for specific pool templates"""
    OPTIONS = [
        {"value": "30 psf/ft", "display": "30 psf/ft"},
        {"value": "45 psf/ft", "display": "45 psf/ft"}, 
        {"value": "Custom", "display": "Custom"}
    ]
    
    @classmethod
    def get_options(cls) -> List[Dict[str, str]]:
        """Get available pool standard options"""
        return cls.OPTIONS
    
    @classmethod
    def is_valid(cls, standard: str) -> bool:
        """Validate pool standard option"""
        return standard in [option["value"] for option in cls.OPTIONS]

class TemplateManager:
    """Manages SML cover letter templates and their configurations"""
    
    def __init__(self):
        self.templates: Dict[str, TemplateConfig] = {}
        self._load_template_configurations()
    
    def _load_template_configurations(self) -> None:
        """Load template configurations from JSON file or initialize defaults"""
        try:
            config_path = self._get_config_file_path()
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self._parse_template_configs(config_data)
                    logger.info(f"Loaded {len(self.templates)} template configurations")
            else:
                logger.warning(f"Template config file not found at {config_path}, using defaults")
                self._initialize_sml_templates()
                self._save_template_configurations()
        except Exception as e:
            logger.error(f"Error loading template configurations: {e}")
            self._initialize_sml_templates()
    
    def _get_config_file_path(self) -> str:
        """Get path to template configuration file"""
        templates_dir = getattr(config, 'COVER_LETTER_TEMPLATES_DIR', 
                               os.path.join(os.path.dirname(__file__), '..', '..', '..', 'templates', 'cover_letters'))
        return os.path.join(templates_dir, 'template_config.json')
    
    def _parse_template_configs(self, config_data: Dict) -> None:
        """Parse template configurations from JSON data"""
        for template_id, template_data in config_data.get('templates', {}).items():
            try:
                template_config = TemplateConfig(
                    template_id=template_id,
                    display_name=template_data['display_name'],
                    file_name=template_data['file_name'],
                    template_type=TemplateType(template_data['template_type']),
                    required_fields=template_data.get('required_fields', []),
                    optional_fields=template_data.get('optional_fields', []),
                    description=template_data.get('description', ''),
                    has_engineer_initials=template_data.get('has_engineer_initials', False),
                    has_checked_by=template_data.get('has_checked_by', False),
                    has_pool_standard=template_data.get('has_pool_standard', False),
                    client_format=template_data.get('client_format', 'name_only'),
                    is_active=template_data.get('is_active', True)
                )
                self.templates[template_id] = template_config
            except Exception as e:
                logger.error(f"Error parsing template config for {template_id}: {e}")
    
    def _initialize_sml_templates(self) -> None:
        """Initialize SML-specific template configurations"""
        sml_templates = [
            # General Calculations Template (Different pattern)
            TemplateConfig(
                template_id="general_calc",
                display_name="General Calculations",
                file_name="2025_Digital_SML_General_Calc_Cover.docx",
                template_type=TemplateType.GENERAL_CALCULATIONS,
                required_fields=["Project", "Location", "Client", "Date", "JobNumber", "By"],
                optional_fields=[],
                description="Standard structural calculation cover letter for general projects",
                has_engineer_initials=False,
                has_checked_by=False,
                client_format="name_only"
            ),
            
            # Pool Templates (All follow same pattern but different purposes)
            TemplateConfig(
                template_id="pool_standard",
                display_name="Pool Calculations - Standard",
                file_name="2025_Digital_SML_Pool_Calc_Cover_2026_exp.docx",
                template_type=TemplateType.POOL_STANDARD,
                required_fields=["Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Standard pool structure calculation cover letter",
                has_engineer_initials=True,
                has_checked_by=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_revision",
                display_name="Pool Calculations - Revision",
                file_name="2025_Digital_SML_Pool_Calc_Cover_2026_exp_Revision.docx",
                template_type=TemplateType.POOL_REVISION,
                required_fields=["Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for revisions",
                has_engineer_initials=True,
                has_checked_by=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_shasta_supplemental",
                display_name="Pool Calculations - Shasta Pools SK Supplemental",
                file_name="2025_Digital_SML_Pool_Calc_Cover_2026_exp_Shasta_Pools_SK_Supplemental.docx",
                template_type=TemplateType.POOL_SHASTA_SUPPLEMENTAL,
                required_fields=["Standard", "Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for Shasta Pools SK supplemental reports",
                has_engineer_initials=True,
                has_checked_by=True,
                has_pool_standard=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_sk_supplemental", 
                display_name="Pool Calculations - SK Supplemental",
                file_name="2025_Digital_SML_Pool_Calc_Cover_2026_exp_SK_Supplemental.docx",
                template_type=TemplateType.POOL_SK_SUPPLEMENTAL,
                required_fields=["Standard", "Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for SK supplemental reports",
                has_engineer_initials=True,
                has_checked_by=True,
                has_pool_standard=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_soils_report",
                display_name="Pool Calculations - Soils Report",
                file_name="2025_Digital_SML_Pool_Calc_Cover_2026_exp_Soils_Report.docx", 
                template_type=TemplateType.POOL_SOILS_REPORT,
                required_fields=["Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for soils reports",
                has_engineer_initials=True,
                has_checked_by=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_shasta_standard",
                display_name="Pool Calculations - Shasta Standard",
                file_name="2025_Digital_SML_Pool_Calc_Cover_Shasta_2026_exp.docx",
                template_type=TemplateType.POOL_SHASTA_STANDARD,
                required_fields=["Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for Shasta standard projects", 
                has_engineer_initials=True,
                has_checked_by=True,
                client_format="separate_fields"
            ),
            
            TemplateConfig(
                template_id="pool_shasta_commercial",
                display_name="Pool Calculations - Shasta Commercial",
                file_name="2025_Digital_SML_Pool_Calc_Cover_Shasta_Commercial_2026_exp.docx",
                template_type=TemplateType.POOL_SHASTA_COMMERCIAL,
                required_fields=["Project", "Location", "Client", "ClientAddress", "Date", "JobNumber", "By", "CheckedBy"],
                optional_fields=[],
                description="Pool calculation cover letter for Shasta commercial projects",
                has_engineer_initials=True,
                has_checked_by=True,
                client_format="separate_fields"
            )
        ]
        
        for template in sml_templates:
            self.templates[template.template_id] = template
    
    def _save_template_configurations(self) -> None:
        """Save current template configurations to JSON file"""
        try:
            config_data = {
                "templates": {
                    template_id: {
                        "display_name": template.display_name,
                        "file_name": template.file_name,
                        "template_type": template.template_type.value,
                        "required_fields": template.required_fields,
                        "optional_fields": template.optional_fields,
                        "description": template.description,
                        "has_engineer_initials": template.has_engineer_initials,
                        "has_checked_by": template.has_checked_by,
                        "has_pool_standard": template.has_pool_standard,
                        "client_format": template.client_format,
                        "is_active": template.is_active
                    }
                    for template_id, template in self.templates.items()
                }
            }
            
            config_path = self._get_config_file_path()
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved template configurations to {config_path}")
        except Exception as e:
            logger.error(f"Error saving template configurations: {e}")
    
    def get_available_templates(self) -> List[Dict[str, Any]]:
        """Get list of available templates for UI display"""
        return [
            {
                "template_id": template.template_id,
                "display_name": template.display_name,
                "description": template.description,
                "template_type": template.template_type.value,
                "has_engineer_initials": template.has_engineer_initials,
                "has_checked_by": template.has_checked_by,
                "has_pool_standard": template.has_pool_standard,
                "client_format": template.client_format
            }
            for template in self.templates.values()
            if template.is_active
        ]
    
    def get_pool_templates(self) -> List[Dict[str, Any]]:
        """Get list of pool-specific templates"""
        return [
            {
                "template_id": template.template_id,
                "display_name": template.display_name,
                "description": template.description,
                "template_type": template.template_type.value
            }
            for template in self.templates.values()
            if template.is_active and template.has_engineer_initials
        ]
    
    def get_general_templates(self) -> List[Dict[str, Any]]:
        """Get list of general (non-pool) templates"""
        return [
            {
                "template_id": template.template_id,
                "display_name": template.display_name,
                "description": template.description,
                "template_type": template.template_type.value
            }
            for template in self.templates.values()
            if template.is_active and not template.has_engineer_initials
        ]
    
    def get_template_config(self, template_id: str) -> Optional[TemplateConfig]:
        """Get configuration for specific template"""
        return self.templates.get(template_id)
    
    def validate_template_exists(self, template_id: str) -> bool:
        """Validate that template exists and file is accessible"""
        template_config = self.get_template_config(template_id)
        if not template_config:
            logger.warning(f"Template config not found for: {template_id}")
            return False
        
        template_path = template_config.get_template_path()
        exists = os.path.exists(template_path)
        if not exists:
            logger.warning(f"Template file not found: {template_path}")
        return exists
    
    def get_template_requirements(self, template_id: str) -> Dict[str, Any]:
        """Get field requirements and special flags for specific template"""
        template_config = self.get_template_config(template_id)
        if not template_config:
            return {
                "required_fields": [], 
                "optional_fields": [],
                "has_engineer_initials": False,
                "has_checked_by": False,
                "has_pool_standard": False,
                "client_format": "name_only"
            }
        
        return {
            "required_fields": template_config.required_fields,
            "optional_fields": template_config.optional_fields,
            "has_engineer_initials": template_config.has_engineer_initials,
            "has_checked_by": template_config.has_checked_by,
            "has_pool_standard": template_config.has_pool_standard,
            "client_format": template_config.client_format
        }
    
    def get_engineer_initials_options(self) -> List[Dict[str, str]]:
        """Get available engineer initial options for pool templates"""
        return EngineerInitials.get_options()
    
    def validate_engineer_initials(self, initials: str) -> bool:
        """Validate engineer initials for pool templates"""
        return EngineerInitials.is_valid(initials)
    
    def get_pool_standard_options(self) -> List[Dict[str, str]]:
        """Get available pool standard options for pool templates"""
        return PoolStandardOption.get_options()
    
    def validate_pool_standard(self, standard: str) -> bool:
        """Validate pool standard for pool templates"""
        return PoolStandardOption.is_valid(standard)

# Global instance
template_manager = TemplateManager()