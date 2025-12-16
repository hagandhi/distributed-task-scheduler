import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scheduler.db")
SCHEDULER_TIMEOUT_SECONDS = int(os.getenv("SCHEDULER_TIMEOUT_SECONDS", "30"))
SWEEP_INTERVAL_SECONDS = int(os.getenv("SWEEP_INTERVAL_SECONDS", "10"))
