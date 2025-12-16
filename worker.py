import os
import time
import json
import uuid
import httpx

SCHEDULER_URL = os.getenv("SCHEDULER_URL", "http://127.0.0.1:8000").rstrip("/")
WORKER_ID = os.getenv("WORKER_ID", str(uuid.uuid4())[:8])
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))

def run_sleep(payload: dict) -> None:
    seconds = float(payload.get("seconds", 1))
    time.sleep(max(0.0, seconds))

JOB_HANDLERS = {
    "sleep": run_sleep,
}

def main():
    print(f"[worker {WORKER_ID}] scheduler={SCHEDULER_URL}")
    with httpx.Client(timeout=30) as client:
        while True:
            try:
                r = client.get(f"{SCHEDULER_URL}/next-job", params={"worker_id": WORKER_ID})
                if r.status_code == 204:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue
                r.raise_for_status()
                job = r.json()
                job_id = job["id"]
                job_type = job["job_type"]
                payload = job.get("payload") or {}
                print(f"[worker {WORKER_ID}] got job {job_id} type={job_type} payload={payload}")

                ok = True
                err = None
                try:
                    handler = JOB_HANDLERS[job_type]
                    handler(payload)
                except Exception as e:
                    ok = False
                    err = str(e)

                body = {"success": ok, "error_message": err}
                r2 = client.post(f"{SCHEDULER_URL}/jobs/{job_id}/complete", json=body)
                r2.raise_for_status()
                print(f"[worker {WORKER_ID}] completed job {job_id} success={ok}")
            except Exception as e:
                print(f"[worker {WORKER_ID}] error: {e}")
                time.sleep(2.0)

if __name__ == "__main__":
    main()
