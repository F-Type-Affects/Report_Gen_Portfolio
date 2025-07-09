from dataclasses import dataclass
from dataclasses import dataclass
from typing import Optional, List, Dict
from decimal import Decimal

@dataclass
class Client:
    client_id: str
    name: str
    street1: str
    street2: str
    city: str
    state: str
    zip_code: str
    email: str
    phone: str

    @classmethod
    def from_dict(cls, data):
        """Create a Client instance from a dictionary."""
        address = data.get('address', {}) or {}

        # Extract address fields
        street1 = address.get('street1', '')
        street2 = address.get('street2', '')
        city = address.get('city', '')
        state = address.get('state', '')
        zip_code = address.get('zip', '')

        # Extract email and phone from communications list
        email = ""
        phone = ""
        communications = address.get('communications', []) or []

        # Iterate through communications to find Email, Phone, and Mobile
        for contact in communications:
            type_name = contact.get('typeName', '').lower()
            value = contact.get('value', '')
            if value:
                value = value.strip()
            if type_name == 'email' and not email:
                email = value or ''
            elif type_name == 'phone' and not phone:
                phone = value or ''
            elif type_name == 'mobile' and not phone:
                phone = value or ''

        return cls(
            client_id=str(data.get('id', '')),
            name=data.get('name', ''),
            street1=street1,
            street2=street2,
            city=city,
            state=state,
            zip_code=zip_code,
            email=email,
            phone=phone
        )

@dataclass
class Project:
    project_id: str
    code: str
    name: str
    purchase_order_number: str
    billing_contact: str
    client_id: str
    street1: str
    street2: str
    city: str
    state: str
    zip_code: str

    @classmethod
    def from_dict(cls, data):
        """Create a Project instance from a dictionary."""
        address = data.get('address')

        # Safely handle address if it is not a valid list or dict
        if isinstance(address, list) and address and isinstance(address[0], dict):
            address_dict = address[0]
        elif isinstance(address, dict):
            address_dict = address
        else:
            address_dict = {}

        return cls(
            project_id=str(data.get('id', '')),
            code=data.get('code', ''),
            name=data.get('name', ''),
            purchase_order_number=data.get('purchaseOrderNumber', ''),
            billing_contact=data.get('billingContact', ''),
            client_id=str(data.get('clientId', '')),
            street1=address_dict.get('street1', ''),
            street2=address_dict.get('street2', ''),
            city=address_dict.get('city', ''),
            state=address_dict.get('state', ''),
            zip_code=address_dict.get('zip', '')
        )


@dataclass
class WindData:
    wind_speed: float
    ten_year_mri: float
    twenty_five_year_mri: float
    fifty_year_mri: float
    hundred_year_mri: float
    unit: str = "Vmph"  # Store unit separately

    @classmethod
    def parse_wind_value(cls, value: str) -> float:
        """Convert wind value string to float, removing 'Vmph'"""
        try:
            return float(value.replace("Vmph", "").strip())
        except (ValueError, AttributeError):
            return 0.0

@dataclass
class SeismicData:
    SS: float = 0.0
    S1: float = 0.0
    Fa: float = 0.0
    Fv: Optional[float] = None  # Using None for N/A in seismic data
    SMS: float = 0.0
    SM1: Optional[float] = None
    SDS: float = 0.0
    SD1: Optional[float] = None
    TL: float = 0.0
    PGA: float = 0.0
    PGAM: float = 0.0
    FPGA: float = 0.0
    Ie: float = 0.0
    Cv: float = 0.0
    no_seismic_spectrum: str = ""
    spectrum_note: str = ""
    seismic_design_category: str = ""

    @classmethod
    def parse_seismic_value(cls, value: str) -> Optional[float]:
        """Convert seismic value string to float, handling N/A"""
        if value == "N/A":
            return None
        try:
            return float(value)
        except (ValueError, AttributeError):
            return 0.0

@dataclass
class IceData:
    thickness: float = 0.0
    thickness_unit: str = "in."
    concurrent_temperature: float = 0.0
    temperature_unit: str = "F"
    gust_speed: float = 0.0
    speed_unit: str = "mph"

    @classmethod
    def parse_ice_value(cls, param: str, value: str) -> float:
        """Convert ice value string to float, removing units"""
        try:
            if "Temperature" in param:
                return float(value.replace("F", "").strip())
            elif "Speed" in param:
                return float(value.replace("mph", "").strip())
            else:  # thickness
                return float(value.replace("in.", "").strip())
        except (ValueError, AttributeError):
            return 0.0

@dataclass
class SnowData:
    ground_snow_load_pg: float = 0.0
    ground_snow_load_pg_elevation: float = 0.0
    mapped_elevation: float = 0.0
    load_unit: str = "lb/ft2"
    elevation_unit: str = "ft"

    @classmethod
    def parse_snow_value(cls, param: str, value: str) -> float:
        """Convert snow value string to float, handling units"""
        try:
            if "Elevation" in param:
                return float(value.replace("ft", "").strip())
            else:
                return float(value.split()[0])  # Take first part before unit
        except (ValueError, AttributeError):
            return 0.0

@dataclass
class ASCESummaryData:
    wind_data: WindData
    seismic_data: SeismicData
    ice_data: IceData
    snow_data: SnowData

    @classmethod
    def from_dict(cls, data: Dict):
        """Create an ASCESummaryData instance from a dictionary of scraped data."""
        wind_dict = {}
        seismic_dict = {}
        ice_dict = {}
        snow_dict = {}

        for section, items in data.items():
            for item in items:
                param = item['parameter']
                value = item['value']

                if section == "Wind":
                    if param == "Wind Speed":
                        wind_dict['wind_speed'] = WindData.parse_wind_value(value)
                    elif "MRI" in param:
                        year = param.split('-')[0]
                        if year == "10":
                            wind_dict['ten_year_mri'] = WindData.parse_wind_value(value)
                        elif year == "25":
                            wind_dict['twenty_five_year_mri'] = WindData.parse_wind_value(value)
                        elif year == "50":
                            wind_dict['fifty_year_mri'] = WindData.parse_wind_value(value)
                        elif year == "100":
                            wind_dict['hundred_year_mri'] = WindData.parse_wind_value(value)

                elif section == "Seismic":
                    if param == "NO SEISMIC SPECTRUM":
                        seismic_dict['no_seismic_spectrum'] = value
                    elif param == "Note":
                        seismic_dict['spectrum_note'] = value
                    elif param == "Seismic Design Category":  # Add this case
                        seismic_dict['seismic_design_category'] = value
                    else:
                        seismic_dict[param] = SeismicData.parse_seismic_value(value)

                elif section == "Ice":
                    if param == "Thickness":
                        ice_dict['thickness'] = IceData.parse_ice_value(param, value)
                    elif param == "Concurrent Temperature":
                        ice_dict['concurrent_temperature'] = IceData.parse_ice_value(param, value)
                    elif param == "Gust Speed":
                        ice_dict['gust_speed'] = IceData.parse_ice_value(param, value)

                elif section == "Snow":
                    if "Ground Snow Load, pg" in param:
                        if "(2400.0" in param:
                            snow_dict['ground_snow_load_pg_elevation'] = SnowData.parse_snow_value(param, value)
                        else:
                            snow_dict['ground_snow_load_pg'] = SnowData.parse_snow_value(param, value)
                    elif param == "Mapped Elevation":
                        snow_dict['mapped_elevation'] = SnowData.parse_snow_value(param, value)

        return cls(
            wind_data=WindData(**wind_dict),
            seismic_data=SeismicData(**seismic_dict),
            ice_data=IceData(**ice_dict),
            snow_data=SnowData(**snow_dict)
        )