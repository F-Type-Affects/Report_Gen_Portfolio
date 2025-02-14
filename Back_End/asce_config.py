from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class StandardVersion(Enum):
    ASCE_7_10 = "7-10"
    ASCE_7_16 = "7-16"
    ASCE_7_22 = "7-22"
    ASCE_41_17 = "41-17"
    ASCE_41_23 = "41-23"

class RiskCategory(Enum):
    I = "1"
    II = "2"
    III = "3"
    IV = "4"

@dataclass
class ASCEToolConfig:
    """Configuration class for ASCE Hazard Tool options"""
    
    @staticmethod
    def get_soil_class_options() -> Dict[str, Dict[str, str]]:
        return {
            "7-10": {
                "0": "A - Hard Rock",
                "1": "B - Rock",
                "2": "C - Very Dense Soil and Soft Rock",
                "3": "D - Stiff Soil",
                "4": "E - Soft Clay Soil",
                "5": "F - Site Response Analysis"
            },
            "7-16": {
                "0": "A - Hard Rock",
                "1": "B - Rock",
                "2": "B - Estimated (see Section 11.4.3)",
                "3": "C - Very Dense Soil and Soft Rock",
                "4": "D - Stiff Soil",
                "5": "D - Default (see Section 11.4.3)",
                "6": "E - Soft Clay Soil",
                "7": "F - Site Response Analysis"
            },
            "7-22": {
                "0": "Default",
                "1": "A - Hard Rock",
                "2": "B - Rock",
                "3": "BC",
                "4": "C - Very Dense Soil and Soft Rock",
                "5": "CD",
                "6": "D - Stiff Soil",
                "7": "DE",
                "8": "E - Soft Clay Soil"
            }
        }
    
    @classmethod
    def get_standard_versions(cls) -> List[str]:
        """Returns list of valid standard versions"""
        return [version.value for version in StandardVersion]

    @classmethod
    def get_risk_categories(cls) -> List[str]:
        """Returns list of valid risk categories"""
        return [category.value for category in RiskCategory]

    @classmethod
    def get_soil_classes(cls, standard_version: str) -> Optional[Dict[str, str]]:
        """
        Returns soil class options for given standard version
        """
        return cls.get_soil_class_options().get(standard_version)

    @classmethod
    def validate_selections(cls, standard_version: str, risk_category: str, soil_class: str) -> bool:
        """
        Validates user selections against allowed values
        """
        # Check standard version
        if standard_version not in cls.get_standard_versions():
            return False
            
        # Check risk category
        if risk_category not in cls.get_risk_categories():
            return False
            
        # Check soil class
        soil_classes = cls.get_soil_classes(standard_version)
        if not soil_classes or soil_class not in soil_classes:
            return False
            
        return True