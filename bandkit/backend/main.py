from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.musicians import router as musicians_router
from src.api.songs import router as songs_router
from src.api.events import router as events_router
from src.api.setlists import router as setlists_router
from src.api.executions import router as executions_router

app = FastAPI(title="BandKit API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(musicians_router)
app.include_router(songs_router)
app.include_router(events_router)
app.include_router(setlists_router)
app.include_router(executions_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "BandKit API"}
