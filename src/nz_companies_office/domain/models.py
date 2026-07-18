"""Domain models for NZ Companies Register entities."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date


class CompanyStatus(StrEnum):
    """Legal status of a company on the register."""

    REGISTERED = "Registered"
    REMOVED = "Removed"


class AddressType(StrEnum):
    """Classification of a company address."""

    REGISTERED_OFFICE = "registered_office"
    SERVICE = "service"


@dataclass
class Address:
    """Physical or service address for a company."""

    address_type: AddressType
    street: str
    suburb: str | None = None
    city: str | None = None
    postcode: str | None = None
    country: str = "New Zealand"


@dataclass
class Director:
    """Individual serving as a director of a company."""

    name: str
    role: str | None = None
    appointment_date: date | None = None


@dataclass
class Shareholder:
    """Entity holding shares in a company."""

    name: str
    share_count: int
    share_type: str | None = None
    company_number: str | None = None


@dataclass
class Company:
    """A company registered on the NZ Companies Register."""

    company_number: str
    name: str
    status: CompanyStatus = CompanyStatus.REGISTERED
    entity_type: str | None = None
    incorporation_date: date | None = None
    addresses: list[Address] = field(default_factory=list)
    directors: list[Director] = field(default_factory=list)
    shareholders: list[Shareholder] = field(default_factory=list)
    nzbn: str | None = None
