"""One-off backfill: assigns company_id and seniority to contacts imported before
the Company/seniority/favorites schema existed. Safe to re-run (idempotent)."""

from src.db.database import SessionLocal
from src.models.models import Contact
from src.services.companies import get_or_create_company
from src.services.seniority import classify_seniority


def main() -> None:
    db = SessionLocal()
    try:
        contacts = db.query(Contact).all()
        updated_company = 0
        updated_seniority = 0
        for contact in contacts:
            if contact.company and contact.company_id is None:
                contact.company_id = get_or_create_company(db, contact.company).id
                updated_company += 1
            new_seniority = classify_seniority(contact.position)
            if contact.seniority != new_seniority:
                contact.seniority = new_seniority
                updated_seniority += 1
        db.commit()
        print(f"Contatos processados: {len(contacts)}")
        print(f"company_id atribuído: {updated_company}")
        print(f"seniority (re)calculado: {updated_seniority}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
