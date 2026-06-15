#!/usr/bin/env python3
"""写入演示数据到数据库：python scripts/seed_demo_data.py"""

from app.api.routes.system import DEMO_STATIONS, DEMO_TASKS, DEMO_VEHICLES
from app.database import Base, SessionLocal, engine
from app.models import ChargeStation, TaskInfo, VehicleInfo


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for row in DEMO_VEHICLES:
            if not db.get(VehicleInfo, row["vehicle_id"]):
                db.add(VehicleInfo(**row))
        for row in DEMO_TASKS:
            if not db.get(TaskInfo, row["task_id"]):
                db.add(TaskInfo(**row))
        for row in DEMO_STATIONS:
            if not db.get(ChargeStation, row["station_id"]):
                db.add(ChargeStation(**row))
        db.commit()
        print("演示数据已写入：")
        print("  车辆:", [v["vehicle_id"] for v in DEMO_VEHICLES])
        print("  订单:", [t["task_id"] for t in DEMO_TASKS])
        print("  充电站:", [s["station_id"] for s in DEMO_STATIONS])
    finally:
        db.close()


if __name__ == "__main__":
    main()
