from pydantic import BaseModel, Field


class ScheduleRequest(BaseModel):
    vehicle_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    algorithm: str = "mamba_ppo"
    use_demo: bool = True
    battery_capacity_kwh: float = Field(default=60.0, gt=0)
    initial_soc: float = Field(default=0.25, ge=0.0, le=1.0)
    soh: float = Field(default=0.95, ge=0.0, le=1.0)
    speed_kmh: float = Field(default=40.0, gt=0)
    temperature: float = 25.0
    train_episodes: int | None = Field(default=None, description="若提供则先训练再推理")


class ScheduleResponse(BaseModel):
    route_id: str
    cost: float
    runtime: float
    route_data: dict | None = None


class TrainRequest(BaseModel):
    algorithm: str = "mamba_ppo"
    episodes: int = Field(default=200, ge=10, le=5000)
