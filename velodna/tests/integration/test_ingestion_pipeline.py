import pytest
import duckdb
from pathlib import Path
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.catalog_store import CatalogStore
FIXTURES = Path("tests/fixtures")

@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    CatalogStore(conn).initialize_schema()
    yield conn
    conn.close()

def test_pipeline_ingest_fit_persists_to_duckdb(db):
    pipeline = IngestionPipeline(db)
    pipeline.ingest_fit(FIXTURES / "sample.fit")
    activities = db.execute("SELECT * FROM activities").fetchall()
    assert len(activities) == 1
    streams = db.execute("SELECT COUNT(*) FROM activity_streams").fetchone()[0]
    assert streams > 0
    act = db.execute("SELECT sport_type, duration_s FROM activities").fetchone()
    assert act[0] == "cycling"
    assert act[1] > 0
