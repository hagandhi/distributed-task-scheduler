from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

def test_create_and_claim_and_complete():
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)

    # create job
    r = client.post("/jobs", json={"job_type": "sleep", "payload": {"seconds": 0}, "priority": 10})
    assert r.status_code == 201
    job = r.json()
    job_id = job["id"]
    assert job["state"] == "PENDING"

    # claim job
    r = client.get("/next-job", params={"worker_id": "w1"})
    assert r.status_code == 200
    claimed = r.json()
    assert claimed["id"] == job_id
    assert claimed["state"] == "RUNNING"
    assert claimed["attempts"] == 1

    # complete job
    r = client.post(f"/jobs/{job_id}/complete", json={"success": True})
    assert r.status_code == 200
    done = r.json()
    assert done["state"] == "COMPLETED"

    # get job
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["state"] == "COMPLETED"
