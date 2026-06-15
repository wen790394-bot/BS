#!/usr/bin/env python3
"""从 CSV 或 JSON 导入样例数据到数据库。

用法:
  cd backend
  python scripts/import_sample_data.py
  python scripts/import_sample_data.py --json data/sample/demo_dataset.json
  python scripts/import_sample_data.py --csv-dir data/sample
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import ChargeStation, TaskInfo, VehicleInfo

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"


def _normalize_location(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    if "," in text and " " not in text.replace(" ", ""):
        parts = text.split(",")
        if len(parts) == 2:
            return f"{parts[0].strip()},{parts[1].strip()}"
    return text


def _parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def load_csv_dir(csv_dir: Path) -> dict[str, list[dict]]:
    vehicles_path = csv_dir / "vehicles.csv"
    tasks_path = csv_dir / "tasks.csv"
    stations_path = csv_dir / "charge_stations.csv"

    def read_csv(path: Path) -> list[dict]:
        with path.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    vehicles = []
    for row in read_csv(vehicles_path):
        vehicles.append(
            {
                "vehicle_id": row["vehicle_id"],
                "capacity": float(row["capacity"]),
                "soc": float(row["soc"]),
                "soh": float(row["soh"]),
                "location": _normalize_location(row.get("location")),
            }
        )

    tasks = []
    for row in read_csv(tasks_path):
        tasks.append(
            {
                "task_id": row["task_id"],
                "location": _normalize_location(row["location"]) or row["location"],
                "demand": float(row["demand"]),
                "service_time": float(row["service_time"]),
                "time_window_start": _parse_float(row.get("time_window_start")),
                "time_window_end": _parse_float(row.get("time_window_end")),
            }
        )

    stations = []
    for row in read_csv(stations_path):
        stations.append(
            {
                "station_id": row["station_id"],
                "location": _normalize_location(row.get("location")),
                "price": float(row["price"]),
                "queue": int(float(row["queue"])),
            }
        )

    return {"vehicles": vehicles, "tasks": tasks, "charge_stations": stations}


def load_json(json_path: Path) -> dict[str, list[dict]]:
    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        "vehicles": data.get("vehicles", []),
        "tasks": data.get("tasks", []),
        "charge_stations": data.get("charge_stations", []),
    }


def import_rows(data: dict[str, list[dict]]) -> dict[str, int]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created = {"vehicles": 0, "tasks": 0, "stations": 0}
    try:
        for row in data["vehicles"]:
            if not db.get(VehicleInfo, row["vehicle_id"]):
                db.add(VehicleInfo(**row))
                created["vehicles"] += 1

        for row in data["tasks"]:
            if not db.get(TaskInfo, row["task_id"]):
                db.add(TaskInfo(**row))
                created["tasks"] += 1

        for row in data["charge_stations"]:
            if not db.get(ChargeStation, row["station_id"]):
                db.add(ChargeStation(**row))
                created["stations"] += 1

        db.commit()
    finally:
        db.close()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="导入样例 CSV/JSON 到数据库")
    parser.add_argument("--json", type=Path, help="JSON 数据集路径")
    parser.add_argument("--csv-dir", type=Path, help="包含三张 CSV 的目录")
    args = parser.parse_args()

    if args.json:
        data = load_json(args.json)
        source = str(args.json)
    elif args.csv_dir:
        data = load_csv_dir(args.csv_dir)
        source = str(args.csv_dir)
    else:
        data = load_json(SAMPLE_DIR / "demo_dataset.json")
        source = str(SAMPLE_DIR / "demo_dataset.json")

    created = import_rows(data)
    print(f"数据来源: {source}")
    print(f"新增记录: 车辆 {created['vehicles']}，订单 {created['tasks']}，充电站 {created['stations']}")
    print("车辆:", [v["vehicle_id"] for v in data["vehicles"]])
    print("订单:", [t["task_id"] for t in data["tasks"]])
    print("充电站:", [s["station_id"] for s in data["charge_stations"]])


if __name__ == "__main__":
    main()
