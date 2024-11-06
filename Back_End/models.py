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

        # Extract address fields
        street1 = address.get('street1', '')
        street2 = address.get('street2', '')
        city = address.get('city', '')
        state = address.get('state', '')
        zip_code = address.get('zip', '')

        # Extract email and phone from communications list
        email = ""
        phone = ""
        communications = address.get('communications', [])
        for contact in communications:
            if contact.get('typeName') == 'Email':
                email = contact.get('value', '')
            elif contact.get('typeName') == 'Mobile':
                phone = contact.get('value', '')

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
