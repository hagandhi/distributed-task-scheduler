from fastapi import FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import text
import threading
import time

from .database import Base, engine, SessionLocal
from .config import SCHEDULER_TIMEOUT_SECONDS, SWEEP_INTERVAL_SECONDS
from .repository import JobRepository
from .routers.jobs import router as jobs_router
from .routers.worker import router as worker_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Distributed Task Scheduler",
    description="Scheduler API that assigns jobs to polling workers. See /docs for Swagger UI.",
    version="1.0.0",
)

app.include_router(jobs_router)
app.include_router(worker_router)

def sweeper_loop():
    # Background sweeper inside scheduler process (simple reliability requirement)
    while True:
        try:
            db: Session = SessionLocal()
            try:
                repo = JobRepository(db)
                repo.sweep_timeouts(timeout_seconds=SCHEDULER_TIMEOUT_SECONDS)
            finally:
                db.close()
        except Exception:
            # Keep it simple; in production you would log properly
            pass
        time.sleep(max(1, SWEEP_INTERVAL_SECONDS))

@app.on_event("startup")
def start_sweeper():
    t = threading.Thread(target=sweeper_loop, daemon=True)
    t.start()

@app.get("/", tags=["root"])
def root():
    return {"status": "ok", "swagger": "/docs"}
