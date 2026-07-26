import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.models import Company

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_company_name(name: str) -> str:
    return _WHITESPACE_RE.sub(" ", name).strip().lower()


def get_or_create_company(db: Session, raw_name: str) -> Company:
    normalized = normalize_company_name(raw_name)
    existing = db.scalar(select(Company).where(Company.normalized_name == normalized))
    if existing:
        return existing

    display_name = _WHITESPACE_RE.sub(" ", raw_name).strip()
    company = Company(name=display_name, normalized_name=normalized)
    db.add(company)
    db.flush()
    return company
