"""mappers.py — преобразование ORM-модели арендодателя в доменную сущность."""

from __future__ import annotations

from features.landlords.domain.entities import Landlord

from .models import LandlordModel


def landlord_to_domain(model: LandlordModel) -> Landlord:
    """Строка landlords (ORM) → доменный Landlord."""
    return Landlord(
        name=model.name,
        contact_person=model.contact_person,
        phone=model.phone,
        email=model.email,
        id=model.id,
    )
