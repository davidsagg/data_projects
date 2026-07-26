from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from src.models.models import ContactSource, InteractionType


class GroupBase(BaseModel):
    name: str
    color: str = "#6366f1"


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class GroupOut(GroupBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class InteractionBase(BaseModel):
    type: InteractionType = InteractionType.note
    content: str = ""
    occurred_at: datetime | None = None


class InteractionCreate(InteractionBase):
    pass


class InteractionOut(InteractionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contact_id: int
    occurred_at: datetime
    created_at: datetime


class ReminderBase(BaseModel):
    due_date: date
    note: str | None = None


class ReminderCreate(ReminderBase):
    pass


class ReminderUpdate(BaseModel):
    due_date: date | None = None
    note: str | None = None
    is_done: bool | None = None


class ReminderOut(ReminderBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    contact_id: int
    is_done: bool
    created_at: datetime
    completed_at: datetime | None = None


class ContactBase(BaseModel):
    first_name: str = ""
    last_name: str = ""
    linkedin_url: str | None = None
    email: str | None = None
    company: str | None = None
    position: str | None = None
    connected_on: date | None = None
    city: str | None = None
    country: str | None = None


class ContactCreate(ContactBase):
    is_favorite: bool = False


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    company: str | None = None
    position: str | None = None
    connected_on: date | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    is_favorite: bool | None = None


class ContactListItem(ContactBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int | None = None
    sector: str | None = None
    seniority: str | None = None
    is_favorite: bool = False
    latitude: float | None = None
    longitude: float | None = None
    source: ContactSource
    groups: list[GroupOut] = []
    last_contacted_at: datetime | None = None


class ContactOut(ContactListItem):
    interactions: list[InteractionOut] = []
    reminders: list[ReminderOut] = []


class ContactPage(BaseModel):
    items: list[ContactListItem]
    total: int
    page: int
    page_size: int


class ImportSummary(BaseModel):
    created: int
    updated: int
    skipped_blank: int
    total_rows: int


class GeocodeResult(BaseModel):
    company_name: str
    found: bool
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class BulkGeocodeResult(BaseModel):
    processed: int
    remaining: int
    results: list[GeocodeResult]


class FacetItem(BaseModel):
    value: str
    count: int
    id: int | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    sector: str | None = None
    contact_count: int = 0


class CompanyUpdate(BaseModel):
    name: str | None = None
    sector: str | None = None


class CompanyDetail(CompanyOut):
    seniority_breakdown: list[FacetItem] = []
    contacts: list[ContactListItem] = []


class BulkSectorRequest(BaseModel):
    company_ids: list[int]
    sector: str


class StatsOut(BaseModel):
    total_contacts: int
    total_groups: int
    contacts_missing_city: int
    total_favorites: int
    top_companies: list[FacetItem]
    contacts_by_group: list[FacetItem]
    connections_by_year: list[FacetItem]
    top_sectors: list[FacetItem]
    seniority_breakdown: list[FacetItem]
    upcoming_reminders: list[ReminderOut]
    recent_contacts: list[ContactListItem]
    favorite_contacts: list[ContactListItem]
