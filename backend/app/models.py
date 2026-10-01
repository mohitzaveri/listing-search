from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Listing:
    id: str
    source: str
    address: str
    city: str
    state: str
    zip: str
    price: float
    bedrooms: int
    bathrooms: float
    sqft: int
    latitude: float
    longitude: float
    listed_date: date
    status: str
    description: str

    @classmethod
    def from_dict(cls, raw: dict) -> "Listing":
        """Build a Listing from one record of the feed JSON (camelCase keys)."""
        return cls(
            id=str(raw["id"]),
            source=raw["source"],
            address=raw["address"],
            city=raw["city"],
            state=raw["state"],
            zip=raw["zip"],
            price=float(raw["price"]),
            bedrooms=int(raw["bedrooms"]),
            bathrooms=float(raw["bathrooms"]),
            sqft=int(raw["sqft"]),
            latitude=float(raw["latitude"]),
            longitude=float(raw["longitude"]),
            listed_date=date.fromisoformat(raw["listedDate"]),
            status=raw["status"],
            description=raw["description"],
        )

    def to_dict(self) -> dict:
        """Back to the camelCase shape the frontend expects."""
        return {
            "id": self.id,
            "source": self.source,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "zip": self.zip,
            "price": self.price,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "sqft": self.sqft,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "listedDate": self.listed_date.isoformat(),
            "status": self.status,
            "description": self.description,
        }
