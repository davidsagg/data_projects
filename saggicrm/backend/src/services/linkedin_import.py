import csv
import io
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.models import Contact, ContactSource
from src.models.schemas import ImportSummary
from src.services.companies import get_or_create_company
from src.services.seniority import classify_seniority

_WHITESPACE_RE = re.compile(r"\s+")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = _WHITESPACE_RE.sub(" ", value).strip()
    return value or None


def _parse_connected_on(value: str | None):
    value = _clean(value)
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d %b %Y").date()
    except ValueError:
        return None


def _find_header_start(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if line.startswith("First Name"):
            return i
    raise ValueError("Cabeçalho 'First Name' não encontrado no CSV de conexões do LinkedIn")


def import_linkedin_csv(db: Session, file_content: bytes) -> ImportSummary:
    text = file_content.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    header_start = _find_header_start(lines)
    reader = csv.DictReader(io.StringIO("".join(lines[header_start:])))

    created = 0
    updated = 0
    skipped_blank = 0
    total_rows = 0

    for row in reader:
        total_rows += 1
        first_name = _clean(row.get("First Name")) or ""
        last_name = _clean(row.get("Last Name")) or ""
        if not first_name and not last_name:
            skipped_blank += 1
            continue

        linkedin_url = _clean(row.get("URL"))
        email = _clean(row.get("Email Address"))
        company = _clean(row.get("Company"))
        position = _clean(row.get("Position"))
        connected_on = _parse_connected_on(row.get("Connected On"))

        existing = None
        if linkedin_url:
            existing = db.scalar(select(Contact).where(Contact.linkedin_url == linkedin_url))
        if existing is None:
            query = select(Contact).where(
                func.lower(Contact.first_name) == first_name.lower(),
                func.lower(Contact.last_name) == last_name.lower(),
            )
            if company:
                query = query.where(func.lower(Contact.company) == company.lower())
            existing = db.scalar(query)

        if existing:
            existing.first_name = first_name
            existing.last_name = last_name
            existing.email = email or existing.email
            existing.company = company or existing.company
            existing.position = position or existing.position
            existing.connected_on = connected_on or existing.connected_on
            if not existing.linkedin_url and linkedin_url:
                existing.linkedin_url = linkedin_url
            existing.company_id = (
                get_or_create_company(db, existing.company).id if existing.company else None
            )
            existing.seniority = classify_seniority(existing.position)
            updated += 1
        else:
            company_id = get_or_create_company(db, company).id if company else None
            db.add(
                Contact(
                    first_name=first_name,
                    last_name=last_name,
                    linkedin_url=linkedin_url,
                    email=email,
                    company=company,
                    company_id=company_id,
                    position=position,
                    seniority=classify_seniority(position),
                    connected_on=connected_on,
                    source=ContactSource.linkedin_import,
                )
            )
            created += 1

    db.commit()
    return ImportSummary(
        created=created, updated=updated, skipped_blank=skipped_blank, total_rows=total_rows
    )
