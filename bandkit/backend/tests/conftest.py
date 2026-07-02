import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from src.db.database import Base, get_db
from src.models.models import Musician, Song


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    from main import app
    def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_musician(db_session):
    m = Musician(name="Dave", instrument="guitarra", role="admin")
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


@pytest.fixture
def sample_song(db_session):
    bkcp = "{title: Garota de Ipanema}\n{key: F}\n[Intro]\n[F][G7]\n"
    s = Song(
        title="Garota de Ipanema",
        artist="Tom Jobim",
        key_original="F",
        bkcp_content=bkcp,
        parse_status="parsed",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s
