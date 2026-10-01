import json
from pathlib import Path

from app.models import Listing

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_listings.json"


def load_listings(path: Path = DATA_FILE) -> list[Listing]:
    with path.open() as file:
        return [Listing.from_dict(raw) for raw in json.load(file)]
