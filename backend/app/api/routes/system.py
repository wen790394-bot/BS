"""系统信息与演示数据初始化。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChargeStation, TaskInfo, VehicleInfo
from app.services.rl.device import device_info

router = APIRouter()

DEMO_VEHICLES = [
    {
        "vehicle_id": "EV-001",
        "capacity": 60.0,
        "soc": 0.25,
        "soh": 0.95,
        "location": "0,0",
    },
]

DEMO_TASKS = [
    {"task_id": "T1", "location": "8.0,3.0", "demand": 1.0, "service_time": 15.0, "time_window_start": 60.0, "time_window_end": 300.0},
    {"task_id": "T2", "location": "12.0,8.0", "demand": 1.0, "service_time": 10.0, "time_window_start": 120.0, "time_window_end": 400.0},
    {"task_id": "T3", "location": "5.0,10.0", "demand": 1.0, "service_time": 12.0, "time_window_start": 180.0, "time_window_end": 500.0},
    {"task_id": "T4", "location": "15.0,2.0", "demand": 1.0, "service_time": 8.0, "time_window_start": 240.0, "time_window_end": 600.0},
    {"task_id": "T5", "location": "10.0,12.0", "demand": 1.0, "service_time": 10.0, "time_window_start": 300.0, "time_window_end": 700.0},
]

DEMO_STATIONS = [
    {"station_id": "S1", "location": "6.0,6.0", "price": 1.0, "queue": 1},
    {"station_id": "S2", "location": "14.0,6.0", "price": 1.5, "queue": 0},
]


@router.get("/info")
def system_info():
    """返回 GPU / Mamba 后端 / RL 模式信息。"""
    return device_info()


@router.post("/seed-demo")
def seed_demo_data(db: Session = Depends(get_db)):
    """写入与内置 demo 一致的车辆、订单、充电站数据。"""
    created = {"vehicles": 0, "tasks": 0, "stations": 0}

    for row in DEMO_VEHICLES:
        if not db.get(VehicleInfo, row["vehicle_id"]):
            db.add(VehicleInfo(**row))
            created["vehicles"] += 1

    for row in DEMO_TASKS:
        if not db.get(TaskInfo, row["task_id"]):
            db.add(TaskInfo(**row))
            created["tasks"] += 1

    for row in DEMO_STATIONS:
        if not db.get(ChargeStation, row["station_id"]):
            db.add(ChargeStation(**row))
            created["stations"] += 1

    db.commit()
    return {
        "status": "ok",
        "created": created,
        "vehicle_ids": [v["vehicle_id"] for v in DEMO_VEHICLES],
        "task_ids": [t["task_id"] for t in DEMO_TASKS],
        "station_ids": [s["station_id"] for s in DEMO_STATIONS],
        "hint": "可用 vehicle_ids=[EV-001], task_ids=[T1..T5] 调用 /decision/run 且 use_demo=false",
    }
