from fastapi import APIRouter

from app.schemas.battery import (
    BatteryHealthRequest,
    BatteryHealthResponse,
    BatteryParamsResponse,
    DegradationCostRequest,
    DegradationCostResponse,
    DegradationPredictRequest,
    DegradationPredictResponse,
    SOCEstimateRequest,
    SOCEstimateResponse,
    SOCSimulateRequest,
    SOCSimulateResponse,
)
from app.services.battery.battery_params import DEFAULT_PARAMS
from app.services.battery.degradation_cost import DegradationCostService
from app.services.battery.soc_model import SOCModel
from app.services.battery.soh_model import SOHModel

router = APIRouter()
soh_model = SOHModel()
soc_model = SOCModel()
degradation_service = DegradationCostService()


@router.get("/params", response_model=BatteryParamsResponse)
def get_battery_params():
    """获取默认电池包参数。"""
    p = DEFAULT_PARAMS
    return BatteryParamsResponse(
        capacity_kwh=p.capacity_kwh,
        nominal_voltage=p.nominal_voltage,
        battery_cost=p.battery_cost,
        soh_eol=p.soh_eol,
        capacity_ah=p.capacity_ah,
    )


@router.post("/health", response_model=BatteryHealthResponse)
def evaluate_battery_health(payload: BatteryHealthRequest):
    """电池健康评估：退化率、RUL 与退化成本。"""
    health = soh_model.estimate(
        soc=payload.soc,
        soh=payload.soh,
        dod=payload.dod,
        temperature=payload.temperature,
        duration_hours=payload.duration_hours,
    )
    cost = degradation_service.compute(health["delta_soh"], payload.battery_cost)
    return BatteryHealthResponse(**health, degradation_cost=cost["degradation_cost"])


@router.post("/soc/estimate", response_model=SOCEstimateResponse)
def estimate_soc(payload: SOCEstimateRequest):
    """ECM + EKF 在线 SOC 估计（单步）。"""
    result = soc_model.estimate(
        current=payload.current,
        voltage=payload.voltage,
        temperature=payload.temperature,
        dt=payload.dt,
        soc_init=payload.soc_init,
    )
    return SOCEstimateResponse(**result)


@router.post("/soc/simulate", response_model=SOCSimulateResponse)
def simulate_soc(payload: SOCSimulateRequest):
    """对测量序列运行 EKF，返回 SOC 轨迹。"""
    trajectory = soc_model.simulate(payload.measurements, payload.soc_init)
    return SOCSimulateResponse(
        trajectory=[SOCEstimateResponse(**t) for t in trajectory]
    )


@router.post("/degradation-cost", response_model=DegradationCostResponse)
def compute_degradation_cost(payload: DegradationCostRequest):
    """计算单次运营的电池退化成本 C_deg = ΔSOH × C_battery。"""
    result = degradation_service.compute_from_operation(
        soc=payload.soc,
        soh=payload.soh,
        dod=payload.dod,
        temperature=payload.temperature,
        duration_hours=payload.duration_hours,
        battery_cost=payload.battery_cost,
    )
    return DegradationCostResponse(**result)


@router.post("/degradation/predict", response_model=DegradationPredictResponse)
def predict_degradation(payload: DegradationPredictRequest):
    """预测 SOH 随等效循环次数的退化轨迹。"""
    trajectory = soh_model.predict_trajectory(
        soh_init=payload.soh_init,
        dod=payload.dod,
        soc=payload.soc,
        temperature=payload.temperature,
        cycles=payload.cycles,
    )
    eol_cycle = next((t["cycle"] for t in trajectory if t["soh"] <= DEFAULT_PARAMS.soh_eol), None)
    return DegradationPredictResponse(trajectory=trajectory, eol_cycle=eol_cycle)
