#!/usr/bin/env python3
"""在终端直接运行并查看系统结果（无需 Swagger）。

用法:
  cd backend
  python scripts/run_demo.py              # 完整演示：导入数据 + 智能决策
  python scripts/run_demo.py status       # 查看 GPU / Mamba 状态
  python scripts/run_demo.py import       # 导入 demo_dataset.json
  python scripts/run_demo.py decide       # 内置 demo 决策
  python scripts/run_demo.py decide --db    # 使用数据库中的车辆/订单决策
  python scripts/run_demo.py decide --algorithm ppo
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保从 backend 目录运行时能导入 app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.import_sample_data import SAMPLE_DIR, import_rows, load_json
from app.utils.terminal_output import (
    print_header,
    print_import_result,
    print_schedule_result,
    print_system_info,
)
from app.database import SessionLocal
from app.models import TaskInfo, VehicleInfo
from app.services.rl.device import device_info
from app.services.rl.ppo_trainer import PPOTrainer


def cmd_status() -> None:
    print_system_info(device_info())


def cmd_import() -> None:
    json_path = SAMPLE_DIR / "demo_dataset.json"
    data = load_json(json_path)
    created = import_rows(data)
    print_import_result(str(json_path), created, data)


def cmd_decide(algorithm: str, use_db: bool) -> None:
    trainer = PPOTrainer()
    db = SessionLocal()
    try:
        if use_db:
            vehicles = db.query(VehicleInfo).all()
            tasks = db.query(TaskInfo).all()
            if not vehicles or not tasks:
                print("错误: 数据库中没有车辆或订单，请先运行: python scripts/run_demo.py import")
                sys.exit(1)
            vehicle_ids = [v.vehicle_id for v in vehicles]
            task_ids = [t.task_id for t in tasks]
            print_header("智能决策（数据库数据）")
            print(f"  车辆         : {vehicle_ids}")
            print(f"  订单         : {task_ids}")
            print(f"  算法         : {algorithm}")
            result = trainer.infer(
                vehicle_ids=vehicle_ids,
                task_ids=task_ids,
                algorithm=algorithm,
                use_demo=False,
                db=db,
            )
        else:
            print_header("智能决策（内置 Demo）")
            print(f"  算法         : {algorithm}")
            result = trainer.infer(algorithm=algorithm, use_demo=True)

        print_schedule_result(result)
    finally:
        db.close()


def cmd_all(algorithm: str, use_db: bool) -> None:
    cmd_status()
    cmd_import()
    cmd_decide(algorithm=algorithm, use_db=use_db)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="电动物流车调度系统 — 终端演示",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=["all", "status", "import", "decide"],
        help="要执行的命令（默认 all）",
    )
    parser.add_argument(
        "--algorithm",
        default="mamba_ppo",
        choices=["mamba_ppo", "transformer_ppo", "ppo", "ga"],
        help="决策算法",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="decide 时使用数据库中的车辆/订单（需先 import）",
    )
    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "import":
        cmd_import()
    elif args.command == "decide":
        cmd_decide(algorithm=args.algorithm, use_db=args.db)
    else:
        cmd_all(algorithm=args.algorithm, use_db=args.db)


if __name__ == "__main__":
    main()
