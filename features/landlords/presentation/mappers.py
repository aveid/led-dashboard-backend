"""mappers.py (presentation) — доменный Landlord → схема LandlordRead."""

from __future__ import annotations

from features.landlords.domain.entities import Landlord

from .schemas import LandlordRead


def landlord_to_read(landlord: Landlord) -> LandlordRead:
    """Доменный Landlord → схема ответа API."""
    return LandlordRead(
        id=landlord.id,
        name=landlord.name,
        contact_person=landlord.contact_person,
        phone=landlord.phone,
        email=landlord.email,
    )
