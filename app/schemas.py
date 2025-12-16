from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional
from datetime import datetime

from .models import JobState


class JobCreate(BaseModel):
    job_type: str = Field(default="sleep", examples=["sleep"])
    payload: dict[str, Any] = Field(default_factory=dict, examples=[{"seconds": 2}])
    priority: int = Field(ge=1, le=10, default=5)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: str
    job_type: str
    payload: dict[str, Any]
    priority: int
    state: JobState                    
    attempts: int
    max_attempts: int
    assigned_worker_id: Optional[str] = None
    started_at: Optional[datetime] = None    
    completed_at: Optional[datetime] = None  
    last_error: Optional[str] = None


class JobComplete(BaseModel):
    success: bool
    error_message: Optional[str] = None
