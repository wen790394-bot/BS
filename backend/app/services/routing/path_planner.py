"""路径规划编排：加载数据、求解 VRP、计算综合成本。"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.orm import Session

from app.models import ChargeStation, TaskInfo, VehicleInfo
from app.services.battery.battery_params import DEFAULT_PARAMS
from app.services.battery.degradation_cost import DegradationCostService
from app.services.energy.consumption import EnergyConsumptionService
from app.services.energy.vehicle_params import DEFAULT_VEHICLE_PARAMS
from app.services.routing.location import RouteNode, parse_location
from app.services.routing.vrp_solver import RouteSolution, VRPSolver
from app.services.scheduling.charge_scheduler import ChargeScheduler


class PathPlanner:
    def __init__(self):
        self.energy = EnergyConsumptionService()
        self.degradation = DegradationCostService()
        self.charge_scheduler = ChargeScheduler()

    def _build_nodes(
        self,
        depot: RouteNode,
        tasks: list[RouteNode],
        charge_stations: list[RouteNode],
    ) -> dict[str, RouteNode]:
        nodes = {depot.node_id: depot}
        for node in tasks + charge_stations:
            nodes[node.node_id] = node
        return nodes

    def _compute_costs(
        self,
        solution: RouteSolution,
        nodes: dict[str, RouteNode],
        soh: float,
        temperature: float,
    ) -> dict:
        """计算 C_travel + C_energy + C_charge + C_waiting + C_degradation。"""
        vp = DEFAULT_VEHICLE_PARAMS
        c_travel = solution.total_distance_km * vp.cost_per_km
        c_energy = solution.total_energy_kwh * vp.electricity_price

        charge_schedule = self.charge_scheduler.extract_plans(solution, nodes)
        c_charge = charge_schedule.c_charge
        c_waiting = charge_schedule.c_waiting

        c_degradation = 0.0
        delta_soh_total = 0.0
        for leg in solution.legs:
            dod = leg.energy_kwh / DEFAULT_PARAMS.capacity_kwh
            soc_mid = (leg.soc_before + leg.soc_after) / 2.0
            deg = self.degradation.compute_from_operation(
                soc=soc_mid,
                soh=soh,
                dod=dod,
                temperature=temperature,
            )
            c_degradation += deg["degradation_cost"]
            delta_soh_total += deg["delta_soh"]

        c_total = c_travel + c_energy + c_charge + c_waiting + c_degradation
        return {
            "travel": round(c_travel, 2),
            "energy": round(c_energy, 2),
            "charge": round(c_charge, 2),
            "waiting": round(c_waiting, 2),
            "degradation": round(c_degradation, 2),
            "total": round(c_total, 2),
            "delta_soh": round(delta_soh_total, 8),
        }

    def plan_from_data(
        self,
        depot: RouteNode,
        tasks: list[RouteNode],
        charge_stations: list[RouteNode] | None = None,
        battery_capacity_kwh: float = 100.0,
        initial_soc: float = 1.0,
        soh: float = 1.0,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
        method: str = "insertion_2opt",
        optimize_charging: bool = True,
    ) -> dict:
        """根据显式节点数据求解路径。"""
        start = time.perf_counter()
        nodes = self._build_nodes(depot, tasks, charge_stations or [])
        task_ids = [t.node_id for t in tasks]
        charge_ids = [s.node_id for s in (charge_stations or [])]

        solver = VRPSolver(
            nodes=nodes,
            depot_id=depot.node_id,
            energy_service=self.energy,
            battery_capacity_kwh=battery_capacity_kwh,
            speed_kmh=speed_kmh,
            temperature=temperature,
        )
        solution = solver.solve(
            task_ids=task_ids,
            charge_ids=charge_ids,
            initial_soc=initial_soc,
            method=method,
        )

        if optimize_charging and charge_ids:
            solution, schedule = self.charge_scheduler.optimize_charging(
                route=solution.route,
                nodes=nodes,
                battery_capacity_kwh=battery_capacity_kwh,
                initial_soc=initial_soc,
                speed_kmh=speed_kmh,
                temperature=temperature,
            )
        else:
            schedule = self.charge_scheduler.extract_plans(solution, nodes)

        costs = self._compute_costs(solution, nodes, soh, temperature)
        runtime = time.perf_counter() - start

        all_node_ids = set(solution.route)
        node_positions = {
            nid: {"x": nodes[nid].x, "y": nodes[nid].y, "type": nodes[nid].node_type}
            for nid in all_node_ids if nid in nodes
        }

        return {
            "route_id": str(uuid.uuid4()),
            "route": solution.route,
            "feasible": solution.feasible,
            "violation": solution.violation,
            "total_distance_km": solution.total_distance_km,
            "total_time_min": solution.total_time_min,
            "total_energy_kwh": solution.total_energy_kwh,
            "cost_breakdown": costs,
            "charge_plan": {
                "stations": schedule.stations,
                "charge_amounts": schedule.charge_amounts,
                "charge_times": schedule.charge_times,
                "plans": [
                    {
                        "station_id": p.station_id,
                        "arrival_time_min": p.arrival_time_min,
                        "charge_kwh": p.charge_kwh,
                        "charge_time_min": p.charge_time_min,
                        "soc_before": p.soc_before,
                        "soc_after": p.soc_after,
                        "charge_price": p.charge_price,
                        "charge_cost": p.charge_cost,
                        "waiting_time_min": p.waiting_time_min,
                        "queue_wait_min": p.queue_wait_min,
                        "waiting_cost": p.waiting_cost,
                        "total_cost": p.total_cost,
                    }
                    for p in schedule.plans
                ],
                "cost": {
                    "charge": schedule.c_charge,
                    "waiting": schedule.c_waiting,
                    "total": schedule.c_total,
                },
                "optimized": schedule.optimized,
            },
            "legs": [
                {
                    "from": leg.from_node,
                    "to": leg.to_node,
                    "distance_km": leg.distance_km,
                    "travel_time_min": leg.travel_time_min,
                    "energy_kwh": leg.energy_kwh,
                    "soc_before": leg.soc_before,
                    "soc_after": leg.soc_after,
                    "arrival_time": leg.arrival_time,
                    "wait_time_min": leg.wait_time_min,
                    "charge_kwh": leg.charge_kwh,
                    "charge_time_min": leg.charge_time_min,
                }
                for leg in solution.legs
            ],
            "arrival_times": solution.arrival_times,
            "soc_trajectory": solution.soc_trajectory,
            "node_positions": node_positions,
            "runtime_s": round(runtime, 4),
            "method": method,
        }

    def plan(
        self,
        db: Session | None,
        vehicle_id: str,
        task_ids: list[str],
        method: str = "insertion_2opt",
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
        include_charge_stations: bool = True,
        depot_location: str | None = None,
        optimize_charging: bool = True,
    ) -> dict:
        """从数据库加载车辆/订单/充电站并求解。"""
        if db is None:
            raise ValueError("数据库会话不能为空")

        vehicle = db.get(VehicleInfo, vehicle_id)
        if not vehicle:
            raise ValueError(f"车辆 {vehicle_id} 不存在")

        tasks_db = [db.get(TaskInfo, tid) for tid in task_ids]
        missing = [tid for tid, t in zip(task_ids, tasks_db) if t is None]
        if missing:
            raise ValueError(f"订单不存在: {missing}")

        depot_xy = parse_location(depot_location or vehicle.location or "0,0")
        depot = RouteNode(
            node_id="depot",
            x=depot_xy[0],
            y=depot_xy[1],
            node_type="depot",
            service_time=0.0,
            tw_start=0.0,
            tw_end=1440.0,
        )

        tasks = []
        for t in tasks_db:
            assert t is not None
            xy = parse_location(t.location)
            tasks.append(RouteNode(
                node_id=t.task_id,
                x=xy[0],
                y=xy[1],
                node_type="task",
                demand=t.demand,
                service_time=t.service_time or 10.0,
                tw_start=t.time_window_start if t.time_window_start is not None else 0.0,
                tw_end=t.time_window_end if t.time_window_end is not None else 1440.0,
            ))

        charge_stations: list[RouteNode] = []
        if include_charge_stations:
            for station in db.query(ChargeStation).all():
                xy = parse_location(station.location or "0,0")
                charge_stations.append(RouteNode(
                    node_id=station.station_id,
                    x=xy[0],
                    y=xy[1],
                    node_type="charge",
                    service_time=0.0,
                    tw_start=0.0,
                    tw_end=1440.0,
                    charge_price=station.price or 1.2,
                    queue=station.queue or 0,
                ))

        return self.plan_from_data(
            depot=depot,
            tasks=tasks,
            charge_stations=charge_stations,
            battery_capacity_kwh=vehicle.capacity,
            initial_soc=vehicle.soc,
            soh=vehicle.soh,
            speed_kmh=speed_kmh,
            temperature=temperature,
            method=method,
            optimize_charging=optimize_charging,
        )

    @staticmethod
    def demo_instance(
        battery_capacity_kwh: float = 60.0,
        initial_soc: float = 0.25,
        soh: float = 0.95,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
        method: str = "insertion_2opt",
        optimize_charging: bool = True,
    ) -> dict:
        """返回内置演示算例。"""
        planner = PathPlanner()
        depot = RouteNode("depot", 0.0, 0.0, "depot")
        tasks = [
            RouteNode("T1", 8.0, 3.0, "task", service_time=15.0, tw_start=60.0, tw_end=300.0),
            RouteNode("T2", 12.0, 8.0, "task", service_time=10.0, tw_start=120.0, tw_end=400.0),
            RouteNode("T3", 5.0, 10.0, "task", service_time=12.0, tw_start=180.0, tw_end=500.0),
            RouteNode("T4", 15.0, 2.0, "task", service_time=8.0, tw_start=240.0, tw_end=600.0),
            RouteNode("T5", 10.0, 12.0, "task", service_time=10.0, tw_start=300.0, tw_end=700.0),
        ]
        stations = [
            RouteNode("S1", 6.0, 6.0, "charge", charge_power_kw=60.0, charge_price=1.0, queue=1),
            RouteNode("S2", 14.0, 6.0, "charge", charge_power_kw=80.0, charge_price=1.5, queue=0),
        ]
        return planner.plan_from_data(
            depot=depot,
            tasks=tasks,
            charge_stations=stations,
            battery_capacity_kwh=battery_capacity_kwh,
            initial_soc=initial_soc,
            soh=soh,
            speed_kmh=speed_kmh,
            temperature=temperature,
            method=method,
            optimize_charging=optimize_charging,
        )
