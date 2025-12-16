from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job
from ..schemas import JobCreate, JobRead, JobComplete
from ..repository import JobRepository

router = APIRouter(tags=["jobs"])

@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = Job(job_type=payload.job_type, payload=payload.payload, priority=payload.priority)
    repo = JobRepository(db)
    job = repo.create_job(job)
    return job

@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/jobs/{job_id}/complete", response_model=JobRead)
def complete_job(job_id: str, body: JobComplete, db: Session = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.complete_job(job_id, success=body.success, error_message=body.error_message)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
