from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..repository import JobRepository
from ..schemas import JobRead

router = APIRouter(tags=["workers"])

@router.get("/next-job", response_model=JobRead, responses={204: {"description": "No job available"}})
def next_job(worker_id: str, db: Session = Depends(get_db)):
    repo = JobRepository(db)
    job = repo.claim_next_job(worker_id=worker_id)
    if not job:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job
