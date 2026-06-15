from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.routing import RoutePlanRequest, RoutePlanResponse
from app.services.routing.location import RouteNode, parse_location
from app.services.routing.path_planner import PathPlanner

router = APIRouter()
path_planner = PathPlanner()


def _to_route_node(node_input) -> RouteNode:
    x, y = parse_location(node_input.location)
    return RouteNode(
        node_id=node_input.node_id,
        x=x,
        y=y,
        node_type=node_input.node_type,
        demand=node_input.demand,
        service_time=node_input.service_time,
        tw_start=node_input.tw_start,
        tw_end=node_input.tw_end,
        charge_power_kw=node_input.charge_power_kw,
        charge_price=node_input.charge_price,
        queue=node_input.queue,
    )


@router.post("/plan", response_model=RoutePlanResponse)
def plan_route(payload: RoutePlanRequest, db: Session = Depends(get_db)):
    """
    电动物流车路径优化 (EVRPTW)。

    支持三种模式:
    1. use_demo=true — 内置演示算例
    2. 显式传入 depot/tasks/charge_stations
    3. vehicle_id + task_ids 从数据库加载
    """
    try:
        if payload.use_demo:
            result = path_planner.demo_instance(
                battery_capacity_kwh=payload.battery_capacity_kwh,
                initial_soc=payload.initial_soc,
                soh=payload.soh,
                speed_kmh=payload.speed_kmh,
                temperature=payload.temperature,
                method=payload.method,
            )
        elif payload.tasks:
            if payload.depot is None:
                raise HTTPException(status_code=400, detail="请提供 depot 节点")
            depot = _to_route_node(payload.depot)
            tasks = [_to_route_node(t) for t in payload.tasks if t.node_type == "task"]
            stations = [_to_route_node(s) for s in payload.charge_stations if s.node_type == "charge"]
            result = path_planner.plan_from_data(
                depot=depot,
                tasks=tasks,
                charge_stations=stations,
                battery_capacity_kwh=payload.battery_capacity_kwh,
                initial_soc=payload.initial_soc,
                soh=payload.soh,
                speed_kmh=payload.speed_kmh,
                temperature=payload.temperature,
                method=payload.method,
            )
        elif payload.vehicle_id and payload.task_ids:
            result = path_planner.plan(
                db=db,
                vehicle_id=payload.vehicle_id,
                task_ids=payload.task_ids,
                method=payload.method,
                speed_kmh=payload.speed_kmh,
                temperature=payload.temperature,
                include_charge_stations=payload.include_charge_stations,
                depot_location=payload.depot.location if payload.depot else None,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="请设置 use_demo=true，或提供 tasks，或提供 vehicle_id+task_ids",
            )
        return RoutePlanResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/demo", response_model=RoutePlanResponse)
def demo_route():
    """运行内置演示算例，快速验证路径优化。"""
    result = path_planner.demo_instance()
    return RoutePlanResponse(**result)