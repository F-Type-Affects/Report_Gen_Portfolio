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

    @classmethod
    def from_dict(cls, data):
        """Create a Client instance from a dictionary."""
        address = data.get('address', {})
        return cls(
            client_id=str(data.get('id', '')),
            name=data.get('name', ''),
            street1=address.get('street1', ''),
            street2=address.get('street2', ''),
            city=address.get('city', ''),
            state=address.get('state', ''),
            zip_code=address.get('zip', '')
        )

