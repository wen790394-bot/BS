from fastapi import APIRouter

from app.api.routes import (
    battery,
    charge_stations,
    decision,
    routing,
    scheduling,
    tasks,
    vehicles,
)

api_router = APIRouter()
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["车辆管理"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["订单管理"])
api_router.include_router(charge_stations.router, prefix="/charge-stations", tags=["充电站"])
api_router.include_router(battery.router, prefix="/battery", tags=["电池健康"])
api_router.include_router(routing.router, prefix="/routing", tags=["路径规划"])
api_router.include_router(scheduling.router, prefix="/scheduling", tags=["充电调度"])
api_router.include_router(decision.router, prefix="/decision", tags=["智能决策"])
