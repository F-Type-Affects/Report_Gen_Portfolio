from dataclasses import dataclass

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
