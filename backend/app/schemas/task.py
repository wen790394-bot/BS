from pydantic import BaseModel, Field


class TaskBase(BaseModel):
    task_id: str
    location: str
    demand: float = 0.0
    service_time: float = 0.0
    time_window_start: float | None = None
    time_window_end: float | None = None


class TaskCreate(TaskBase):
    pass


class TaskResponse(TaskBase):
    class Config:
        from_attributes = True
