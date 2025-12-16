from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Job, JobState

def utcnow():
    return datetime.now(timezone.utc)

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, job: Job) -> Job:
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self.db.get(Job, job_id)

    def claim_next_job(self, worker_id: str) -> Job | None:
        """Atomically claim next PENDING job, highest priority first.

        Postgres: uses FOR UPDATE SKIP LOCKED.
        SQLite/others: uses compare-and-set UPDATE with rowcount check.
        """
        dialect = self.db.bind.dialect.name if self.db.bind is not None else ""
        now = utcnow()

        if dialect.startswith("postgres"):
            # Best option: row-level lock + skip locked for concurrency.
            q = (
                select(Job)
                .where(Job.state == JobState.PENDING)
                .order_by(Job.priority.desc(), Job.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = self.db.execute(q).scalars().first()
            if not job:
                return None
            job.state = JobState.RUNNING
            job.assigned_worker_id = worker_id
            job.started_at = now
            job.attempts += 1
            self.db.commit()
            self.db.refresh(job)
            return job

        # Generic fallback: fetch candidate then attempt atomic state transition
        q = (
            select(Job.id)
            .where(Job.state == JobState.PENDING)
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .limit(1)
        )
        job_id = self.db.execute(q).scalars().first()
        if not job_id:
            return None

        stmt = (
            update(Job)
            .where(Job.id == job_id, Job.state == JobState.PENDING)
            .values(
                state=JobState.RUNNING,
                assigned_worker_id=worker_id,
                started_at=now,
                attempts=Job.attempts + 1,
                updated_at=now,
            )
        )
        res = self.db.execute(stmt)
        if res.rowcount != 1:
            self.db.rollback()
            return None

        self.db.commit()
        job = self.db.get(Job, job_id)
        return job

    def complete_job(self, job_id: str, success: bool, error_message: str | None) -> Job | None:
        job = self.db.get(Job, job_id)
        if not job:
            return None

        now = utcnow()
        if success:
            job.state = JobState.COMPLETED
            job.completed_at = now
            job.last_error = None
        else:
            job.last_error = error_message or "Job failed"
            # Retry once automatically: if attempts < max_attempts, requeue
            if job.attempts < job.max_attempts:
                job.state = JobState.PENDING
                job.assigned_worker_id = None
                job.started_at = None
            else:
                job.state = JobState.FAILED
                job.completed_at = now

        self.db.commit()
        self.db.refresh(job)
        return job

    def sweep_timeouts(self, timeout_seconds: int) -> int:
        """Detect RUNNING jobs older than timeout and apply retry/failed policy.
        Returns number of jobs transitioned.
        """
        now = utcnow()
        cutoff = now - timedelta(seconds=timeout_seconds)

        q = select(Job).where(Job.state == JobState.RUNNING, Job.started_at != None, Job.started_at < cutoff)
        timed_out = self.db.execute(q).scalars().all()

        transitioned = 0
        for job in timed_out:
            job.last_error = f"Worker timeout after {timeout_seconds}s"
            # If we still have retries left, requeue
            if job.attempts < job.max_attempts:
                job.state = JobState.PENDING
                job.assigned_worker_id = None
                job.started_at = None
            else:
                job.state = JobState.FAILED
                job.completed_at = now
            transitioned += 1

        if transitioned:
            self.db.commit()
        else:
            self.db.rollback()
        return transitioned
