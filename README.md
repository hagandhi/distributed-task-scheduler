# cd (FastAPI + SQLAlchemy)

This project implements the **Distributed Task Scheduler** assessment requirements:
- Create jobs with **payload** and **priority (1–10)**
- Job states: **PENDING → RUNNING → COMPLETED / FAILED**
- Persistence in **Postgres or SQLite**
- **One scheduler process** assigns jobs
- **Multiple workers** poll for jobs and report completion
- Reliability: **retry once** + **timeout detection (30s)**

Swagger/OpenAPI: **`/docs`**

---

## How the scheduler architecture works

### Components

1. **Scheduler API (FastAPI)**
   - This is the *single* scheduler process.
   - Owns the job queue logic and performs **atomic job claiming**.
   - Exposes the HTTP API endpoints used by clients and workers.

2. **Database (Postgres / SQLite)**
   - Stores jobs and their state transitions.
   - Enables coordination between multiple workers via durable state.

3. **Workers (one or many)**
   - Separate processes/containers.
   - Poll the scheduler for work.
   - Execute the job (e.g., `sleep`) and report completion.

4. **Sweeper (background loop inside Scheduler API)**
   - Periodically checks for `RUNNING` jobs that are stuck beyond the timeout (default 30s).
   - Applies reliability rules: requeue (retry once) or mark failed.

---

## Architecture diagram (Excalidraw-style)

```
                         ┌──────────────────────────────────────────┐
                         │              Client / User               │
                         │  (Swagger UI / curl / other caller)      │
                         └───────────────────────┬──────────────────┘
                                                 │  POST /jobs
                                                 │  GET  /jobs/{id}
                                                 ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                         Scheduler API (FastAPI)                            │
│                                                                           │
│  Endpoints:                                                               │
│   • POST /jobs                → persist job as PENDING                     │
│   • GET  /jobs/{id}           → read job status                            │
│   • GET  /next-job?worker_id  → atomic claim (PENDING→RUNNING)             │
│   • POST /jobs/{id}/complete  → finalize or requeue                        │
│                                                                           │
│  Background reliability loop (Sweeper):                                   │
│   • every SWEEP_INTERVAL_SECONDS:                                          │
│       - find RUNNING jobs with started_at older than TIMEOUT               │
│       - if attempts < max_attempts: set back to PENDING (retry once)       │
│       - else: set FAILED                                                   │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                                │ SQL (transactions)
                                ▼
                     ┌──────────────────────────────┐
                     │           Database            │
                     │   jobs table (durable state)  │
                     └───────────────┬──────────────┘
                                     ▲
                                     │
                GET /next-job        │   POST /jobs/{id}/complete
┌──────────────────────────────┐     │     ┌──────────────────────────────┐
│           Worker #1            │────┘────▶│           Worker #N            │
│  loop:                         │          │  loop:                         │
│   - poll /next-job             │          │   - poll /next-job             │
│   - execute job (sleep)        │          │   - execute job (sleep)        │
│   - report /complete           │          │   - report /complete           │
└──────────────────────────────┘          └──────────────────────────────┘
```

### What makes it “distributed”
- The scheduler is a single coordinator (the API).
- Workers are independent processes. You can scale them horizontally.
- Coordination happens via the database state + atomic claim operation.

---

## State machine

```
PENDING  --(claimed via /next-job)-->  RUNNING
RUNNING  --(worker reports success)--> COMPLETED
RUNNING  --(worker reports failure)--> PENDING (retry once) OR FAILED
RUNNING  --(timeout detected)-------> PENDING (retry once) OR FAILED
```

---

## Reliability rules

- **Retry once**: each job has `max_attempts = 2` (1 initial + 1 retry).
- **Worker timeout**: if a job is `RUNNING` and `started_at` is older than 30 seconds:
  - if attempts left → requeue to `PENDING`
  - else → mark `FAILED`

---

## Run (SQLite)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export DATABASE_URL="sqlite:///./scheduler.db"
uvicorn app.main:app --reload
```

Swagger:
- http://127.0.0.1:8000/docs

Worker:
```bash
export SCHEDULER_URL="http://127.0.0.1:8000"
python worker.py
```

---

## Run (Docker, Postgres + API + workers)

```bash
docker compose up --build
```

Scale workers (recommended approach: **single image, many worker containers**):
- If your compose has a `worker` service: `docker compose up --build --scale worker=3`
- If it has `worker1/worker2`, edit compose to a single `worker` service for easier scaling.

---

## Quick demo via Swagger

1. **POST `/jobs`**
   ```json
   {"job_type":"sleep","payload":{"seconds":2},"priority":5}
   ```
2. **GET `/jobs/{id}`** until state becomes `COMPLETED`

---

## Tests

```bash
pytest -q
```
