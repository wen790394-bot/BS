from pydantic import BaseModel, Field


class ChargePlanItemResponse(BaseModel):
    station_id: str
    arrival_time_min: float
    charge_kwh: float
    charge_time_min: float
    soc_before: float
    soc_after: float
    charge_price: float
    charge_cost: float
    waiting_time_min: float
    queue_wait_min: float
    waiting_cost: float
    total_cost: float


class ChargeCostResponse(BaseModel):
    charge: float
    waiting: float
    total: float


class ChargePlanRequest(BaseModel):
    """基于路径规划结果的充电调度请求。"""

    route: list[str] = Field(default_factory=list)
    legs: list[dict] = Field(default_factory=list)
    node_positions: dict[str, dict] = Field(default_factory=dict)
    battery_capacity_kwh: float = Field(default=100.0, gt=0)
    initial_soc: float = Field(default=0.9, ge=0.0, le=1.0)
    speed_kmh: float = Field(default=40.0, gt=0)
    temperature: float = 25.0
    optimize: bool = True


class ChargePlanResponse(BaseModel):
    vehicle_id: str | None = None
    route: list[str] = Field(default_factory=list)
    charge_plan: dict
    cost_breakdown: dict | None = None


class IntegratedPlanRequest(BaseModel):
    """路径规划 + 充电调度联合请求。"""

    use_demo: bool = False
    vehicle_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    battery_capacity_kwh: float = Field(default=60.0, gt=0)
    initial_soc: float = Field(default=0.25, ge=0.0, le=1.0)
    soh: float = Field(default=0.95, ge=0.0, le=1.0)
    speed_kmh: float = Field(default=40.0, gt=0)
    temperature: float = 25.0
    method: str = Field(default="insertion_2opt")
    optimize_charging: bool = True
