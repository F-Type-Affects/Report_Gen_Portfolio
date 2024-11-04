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
        address = data.get('address', {})
        if isinstance(address, list) and address and isinstance(address[0], dict):
            address_dict = address[0]
        else:
            address_dict = {}

        return cls(
            client_id=str(data.get('id', '')),
            name=data.get('name', ''),
            street1=address_dict.get('street1', ''),
            street2=address_dict.get('street2', ''),
            city=address_dict.get('city', ''),
            state=address_dict.get('state', ''),
            zip_code=address_dict.get('zip', ''),
            email=data.get('email', ''),
            phone=data.get('phone', '')
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
        address = data.get('address', [])
        # check if address is list and get first item if it is
        if isinstance(address, list) and address and isinstance(address[0], dict):
            address_dict = address[0]
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
