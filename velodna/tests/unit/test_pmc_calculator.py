import pytest, duckdb
from datetime import date, datetime, timedelta, timezone
from src.analytics.pmc_calculator import PMCCalculator, FTPDetector
from src.ingestion.catalog_store import CatalogStore
from src.ingestion.fit_parser import Activity, ActivityStream

def _tss(days=50, tss=80.0):
    return {date(2024,1,1)+timedelta(i): tss for i in range(days)}

def _streams_power(w=320, secs=1300):
    base=datetime(2024,1,1,8,tzinfo=timezone.utc)
    return [ActivityStream(timestamp=base+timedelta(seconds=i),power_w=w) for i in range(secs)]

def test_ctl_increases_with_consistent_training():
    c=PMCCalculator(); s=c.calculate_ctl(_tss(50,80)); d=sorted(s); assert s[d[-1]]>s[d[0]]

def test_atl_responds_faster_than_ctl():
    c=PMCCalculator(); t=_tss(30,100)
    assert c.calculate_atl(t)[max(t)]>c.calculate_ctl(t)[max(t)]

def test_tsb_is_ctl_minus_atl():
    assert PMCCalculator().calculate_tsb(50.0,60.0)==pytest.approx(-10.0)

def test_ftp_95pct_of_best_20min():
    ftp=FTPDetector().detect(_streams_power(330,1300))
    assert ftp is not None and ftp==pytest.approx(330*0.95,rel=0.05)

def test_ftp_none_when_insufficient():
    assert FTPDetector().detect(_streams_power(320,300)) is None

@pytest.fixture
def db30():
    conn=duckdb.connect(":memory:")
    store=CatalogStore(conn); store.initialize_schema()
    for i in range(30):
        a=Activity(garmin_id=f"r{i}",sport_type="cycling",
            start_time=datetime(2024,1,i+1,8,tzinfo=timezone.utc),
            duration_s=3600,distance_m=40000,elevation_m=300)
        store.upsert_activity(a,f"a{i}")
        conn.execute("UPDATE activities SET tss=80 WHERE activity_id=?",[f"a{i}"])
    yield conn; conn.close()

def test_pmc_stores_metrics(db30):
    store=CatalogStore(db30); PMCCalculator().run_and_store(store,date(2024,1,30))
    assert db30.execute("SELECT COUNT(*) FROM athlete_metrics WHERE ctl IS NOT NULL").fetchone()[0]>0
