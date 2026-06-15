from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.scheduling import (
    ChargePlanRequest,
    ChargePlanResponse,
    IntegratedPlanRequest,
)
from app.services.routing.path_planner import PathPlanner
from app.services.scheduling.charge_scheduler import ChargeScheduler

router = APIRouter()
charge_scheduler = ChargeScheduler()
path_planner = PathPlanner()


@router.post("/plan", response_model=ChargePlanResponse)
def plan_charging(payload: ChargePlanRequest):
    """
    充电调度：基于路径规划结果，决策充电站/充电量/充电时间。

    目标 min(C_charge + C_waiting)。
    """
    if not payload.route or not payload.legs:
        raise HTTPException(status_code=400, detail="请提供 route 与 legs（通常来自路径规划 API 结果）")

    plan = charge_scheduler.plan(
        route=payload.route,
        legs=payload.legs,
        node_meta=payload.node_positions,
        battery_capacity_kwh=payload.battery_capacity_kwh,
        initial_soc=payload.initial_soc,
        speed_kmh=payload.speed_kmh,
        temperature=payload.temperature,
        optimize=payload.optimize,
    )
    return ChargePlanResponse(route=payload.route, charge_plan=plan)


@router.post("/integrated")
def integrated_plan(payload: IntegratedPlanRequest, db: Session = Depends(get_db)):
    """路径规划与充电调度联合求解，返回完整成本 C_total。"""
    try:
        if payload.use_demo:
            result = path_planner.demo_instance(
                battery_capacity_kwh=payload.battery_capacity_kwh,
                initial_soc=payload.initial_soc,
                soh=payload.soh,
                speed_kmh=payload.speed_kmh,
                temperature=payload.temperature,
                method=payload.method,
                optimize_charging=payload.optimize_charging,
            )
        elif payload.vehicle_id and payload.task_ids:
            result = path_planner.plan(
                db=db,
                vehicle_id=payload.vehicle_id,
                task_ids=payload.task_ids,
                method=payload.method,
                speed_kmh=payload.speed_kmh,
                temperature=payload.temperature,
                optimize_charging=payload.optimize_charging,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="请设置 use_demo=true，或提供 vehicle_id + task_ids",
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/demo")
def demo_charging():
    """演示：路径规划 + 充电调度联合算例。"""
    result = path_planner.demo_instance(optimize_charging=True)
    return {
        "route": result["route"],
        "charge_plan": result.get("charge_plan"),
        "cost_breakdown": result["cost_breakdown"],
        "feasible": result["feasible"],
        "total_distance_km": result["total_distance_km"],
        "runtime_s": result["runtime_s"],
    }
