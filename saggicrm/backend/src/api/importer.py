from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.models.schemas import ImportSummary
from src.services.linkedin_import import import_linkedin_csv

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/linkedin", response_model=ImportSummary)
async def import_linkedin(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Envie o arquivo Connections.csv exportado do LinkedIn")
    content = await file.read()
    try:
        return import_linkedin_csv(db, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
