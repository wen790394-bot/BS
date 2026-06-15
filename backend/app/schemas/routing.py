from pydantic import BaseModel, Field


class RouteNodeInput(BaseModel):
    """路径节点输入（depot / 配送点 / 充电站）。"""

    node_id: str
    location: str = Field(description='坐标 "x,y"，单位 km')
    node_type: str = Field(default="task", description="depot | task | charge")
    demand: float = 0.0
    service_time: float = 0.0
    tw_start: float = 0.0
    tw_end: float = 1440.0
    charge_power_kw: float = 60.0
    charge_price: float = 1.2
    queue: int = 0


class RoutePlanRequest(BaseModel):
    """EVRPTW 路径规划请求。"""

    use_demo: bool = False
    depot: RouteNodeInput | None = None
    tasks: list[RouteNodeInput] = Field(default_factory=list)
    charge_stations: list[RouteNodeInput] = Field(default_factory=list)
    vehicle_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    battery_capacity_kwh: float = Field(default=60.0, gt=0)
    initial_soc: float = Field(default=0.25, ge=0.0, le=1.0)
    soh: float = Field(default=0.95, ge=0.0, le=1.0)
    speed_kmh: float = Field(default=40.0, gt=0)
    temperature: float = 25.0
    method: str = Field(default="insertion_2opt", description="insertion_2opt | alns")
    include_charge_stations: bool = True


class CostBreakdownResponse(BaseModel):
    travel: float
    energy: float
    charge: float
    waiting: float
    degradation: float
    total: float
    delta_soh: float | None = None


class RoutePlanResponse(BaseModel):
    route_id: str
    route: list[str] = Field(default_factory=list)
    feasible: bool
    violation: str = ""
    total_distance_km: float
    total_time_min: float
    total_energy_kwh: float
    cost_breakdown: CostBreakdownResponse
    charge_plan: dict = Field(default_factory=dict)
    legs: list[dict] = Field(default_factory=list)
    arrival_times: dict = Field(default_factory=dict)
    soc_trajectory: list[dict] = Field(default_factory=list)
    node_positions: dict = Field(default_factory=dict)
    runtime_s: float
    method: str
