from pydantic import BaseModel, Field


class BatteryHealthRequest(BaseModel):
    vehicle_id: str = ""
    soc: float = Field(ge=0.0, le=1.0, description="当前 SOC")
    soh: float = Field(ge=0.0, le=1.0, description="当前 SOH")
    dod: float = Field(ge=0.0, le=1.0, description="本次放电深度 DOD")
    temperature: float = Field(default=25.0, description="温度 (°C)")
    duration_hours: float = Field(default=0.0, ge=0.0, description="静置/日历老化时长 (h)")
    battery_cost: float | None = Field(default=None, gt=0, description="电池包成本 (元)")


class BatteryHealthResponse(BaseModel):
    soh_t: float
    delta_soh: float
    degradation_rate: float
    rul_t: float
    cycle_degradation: float
    calendar_degradation: float
    degradation_cost: float | None = None


class SOCEstimateRequest(BaseModel):
    current: float = Field(description="电流 (A)，放电为正")
    voltage: float = Field(description="端电压 (V)")
    temperature: float = Field(default=25.0, description="温度 (°C)")
    dt: float = Field(default=1.0, gt=0, description="采样间隔 (s)")
    soc_init: float | None = Field(default=None, ge=0.0, le=1.0)


class SOCEstimateResponse(BaseModel):
    soc: float
    v1: float
    voltage_predicted: float
    voltage_measured: float
    soc_uncertainty: float


class SOCSimulateRequest(BaseModel):
    measurements: list[dict]
    soc_init: float = Field(default=0.8, ge=0.0, le=1.0)


class SOCSimulateResponse(BaseModel):
    trajectory: list[SOCEstimateResponse]


class DegradationCostRequest(BaseModel):
    soc: float = Field(ge=0.0, le=1.0)
    soh: float = Field(ge=0.0, le=1.0)
    dod: float = Field(ge=0.0, le=1.0)
    temperature: float = 25.0
    duration_hours: float = Field(default=0.0, ge=0.0)
    battery_cost: float | None = None


class DegradationCostResponse(BaseModel):
    soh_t: float
    delta_soh: float
    degradation_rate: float
    rul_t: float
    cycle_degradation: float
    calendar_degradation: float
    degradation_cost: float
    battery_cost: float


class DegradationPredictRequest(BaseModel):
    soh_init: float = Field(ge=0.0, le=1.0, default=1.0)
    dod: float = Field(ge=0.0, le=1.0, default=0.8)
    soc: float = Field(ge=0.0, le=1.0, default=0.5)
    temperature: float = 25.0
    cycles: int = Field(default=100, ge=1, le=2000)


class DegradationPredictResponse(BaseModel):
    trajectory: list[dict]
    eol_cycle: int | None = None


class BatteryParamsResponse(BaseModel):
    capacity_kwh: float
    nominal_voltage: float
    battery_cost: float
    soh_eol: float
    capacity_ah: float
