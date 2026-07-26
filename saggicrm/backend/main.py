from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import companies, contacts, geocode, groups, importer, interactions, reminders, stats

app = FastAPI(title="SaggiCRM API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5177"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contacts.router)
app.include_router(companies.router)
app.include_router(groups.router)
app.include_router(interactions.router)
app.include_router(reminders.router)
app.include_router(geocode.router)
app.include_router(importer.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
