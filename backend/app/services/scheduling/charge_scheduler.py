"""
充电调度：充电站选择、充电时间与充电量决策。

目标: min(C_charge + C_waiting)
- C_charge = Σ (充电量 kWh × 站点电价)
- C_waiting = Σ (时间窗等待 + 排队等待) × 等待成本系数
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.energy.consumption import EnergyConsumptionService
from app.services.energy.vehicle_params import DEFAULT_VEHICLE_PARAMS
from app.services.routing.location import RouteNode, travel_time_minutes
from app.services.routing.vrp_solver import RouteLeg, RouteSolution, VRPSolver
from app.services.scheduling.charge_params import DEFAULT_CHARGE_PARAMS, ChargeSchedulingParams


@dataclass
class ChargePlanItem:
    """单次充电计划。"""

    station_id: str
    arrival_time_min: float
    charge_kwh: float
    charge_time_min: float
    soc_before: float
    soc_after: float
    charge_price: float
    charge_cost: float
    waiting_time_min: float
    queue_wait_min: float
    waiting_cost: float
    total_cost: float


@dataclass
class ChargeScheduleResult:
    """充电调度输出。"""

    stations: list[str] = field(default_factory=list)
    charge_amounts: list[float] = field(default_factory=list)
    charge_times: list[float] = field(default_factory=list)
    plans: list[ChargePlanItem] = field(default_factory=list)
    c_charge: float = 0.0
    c_waiting: float = 0.0
    c_total: float = 0.0
    optimized: bool = False


class ChargeScheduler:
    def __init__(
        self,
        params: ChargeSchedulingParams | None = None,
        energy_service: EnergyConsumptionService | None = None,
    ):
        self.params = params or DEFAULT_CHARGE_PARAMS
        self.energy = energy_service or EnergyConsumptionService()

    def _station_price(self, node: RouteNode) -> float:
        return node.charge_price if node.charge_price > 0 else self.params.default_charge_price

    def _queue_wait_min(self, node: RouteNode) -> float:
        return max(0, node.queue) * self.params.queue_wait_per_vehicle_min

    def _leg_waiting_cost(self, wait_time_min: float, queue_wait_min: float) -> float:
        total_wait = wait_time_min + queue_wait_min
        return total_wait * self.params.waiting_cost_per_min

    def extract_plans(
        self,
        solution: RouteSolution,
        nodes: dict[str, RouteNode],
    ) -> ChargeScheduleResult:
        """从路径求解结果中提取充电计划并计算 C_charge + C_waiting。"""
        result = ChargeScheduleResult()
        c_charge = 0.0
        c_waiting = 0.0

        for leg in solution.legs:
            if leg.charge_kwh <= 1e-6:
                continue
            node = nodes.get(leg.to_node)
            if node is None or node.node_type != "charge":
                continue

            price = self._station_price(node)
            queue_wait = self._queue_wait_min(node)
            charge_cost = leg.charge_kwh * price
            waiting_cost = self._leg_waiting_cost(leg.wait_time_min, queue_wait)

            item = ChargePlanItem(
                station_id=leg.to_node,
                arrival_time_min=leg.arrival_time,
                charge_kwh=leg.charge_kwh,
                charge_time_min=leg.charge_time_min,
                soc_before=leg.soc_before,
                soc_after=leg.soc_after,
                charge_price=price,
                charge_cost=round(charge_cost, 2),
                waiting_time_min=leg.wait_time_min,
                queue_wait_min=queue_wait,
                waiting_cost=round(waiting_cost, 2),
                total_cost=round(charge_cost + waiting_cost, 2),
            )

            result.plans.append(item)
            result.stations.append(leg.to_node)
            result.charge_amounts.append(round(leg.charge_kwh, 4))
            result.charge_times.append(round(leg.charge_time_min, 2))
            c_charge += charge_cost
            c_waiting += waiting_cost

        result.c_charge = round(c_charge, 2)
        result.c_waiting = round(c_waiting, 2)
        result.c_total = round(c_charge + c_waiting, 2)
        return result

    def _min_soc_for_remainder(
        self,
        route: list[str],
        start_idx: int,
        nodes: dict[str, RouteNode],
        battery_capacity_kwh: float,
        speed_kmh: float,
    ) -> float:
        """估算从 start_idx 起完成剩余路线所需的最低 SOC。"""
        vp = DEFAULT_VEHICLE_PARAMS
        required_energy = 0.0
        for i in range(start_idx, len(route) - 1):
            from_id, to_id = route[i], route[i + 1]
            if from_id not in nodes or to_id not in nodes:
                continue
            dist = ((nodes[from_id].x - nodes[to_id].x) ** 2 +
                    (nodes[from_id].y - nodes[to_id].y) ** 2) ** 0.5
            required_energy += self.energy.compute_energy(dist, speed_kmh)
        min_soc = required_energy / battery_capacity_kwh + vp.soc_min
        return min(min_soc, vp.charge_target_soc)

    def optimize_charging(
        self,
        route: list[str],
        nodes: dict[str, RouteNode],
        battery_capacity_kwh: float,
        initial_soc: float,
        speed_kmh: float,
        temperature: float,
    ) -> tuple[RouteSolution, ChargeScheduleResult]:
        """
        对已有路线优化各充电站充电量，目标 min(C_charge + C_waiting)。

        对每个充电站，在 [最低需求 SOC, 目标 SOC] 区间内搜索最优充电量。
        """
        vp = DEFAULT_VEHICLE_PARAMS
        solver = VRPSolver(
            nodes=nodes,
            depot_id=route[0],
            energy_service=self.energy,
            battery_capacity_kwh=battery_capacity_kwh,
            speed_kmh=speed_kmh,
            temperature=temperature,
        )

        charge_indices = [
            i for i, node_id in enumerate(route[1:-1], start=1)
            if nodes.get(node_id) and nodes[node_id].node_type == "charge"
        ]

        if not charge_indices:
            solution = solver._evaluate_schedule(route, initial_soc)
            schedule = self.extract_plans(solution, nodes)
            return solution, schedule

        best_route = list(route)
        best_solution = solver._evaluate_schedule(best_route, initial_soc)
        best_schedule = self.extract_plans(best_solution, nodes)
        best_cost = best_schedule.c_total

        for idx in charge_indices:
            station_id = route[idx]
            station = nodes[station_id]
            min_soc = self._min_soc_for_remainder(
                route, idx, nodes, battery_capacity_kwh, speed_kmh,
            )
            arrival_soc = self._estimate_soc_at_node(
                solver, route, idx, initial_soc,
            )
            if arrival_soc >= min_soc:
                continue

            candidates: list[tuple[float, RouteSolution, ChargeScheduleResult]] = []
            soc = max(arrival_soc, min_soc)
            while soc <= vp.charge_target_soc + 1e-6:
                trial_solution = self._simulate_with_charge_at(
                    solver, route, idx, initial_soc, soc, battery_capacity_kwh,
                )
                if trial_solution.feasible:
                    schedule = self.extract_plans(trial_solution, nodes)
                    candidates.append((schedule.c_total, trial_solution, schedule))
                soc += self.params.min_charge_soc_step

            if not candidates:
                trial_solution = self._simulate_with_charge_at(
                    solver, route, idx, initial_soc, vp.charge_target_soc, battery_capacity_kwh,
                )
                schedule = self.extract_plans(trial_solution, nodes)
                candidates.append((schedule.c_total, trial_solution, schedule))

            candidates.sort(key=lambda x: x[0])
            cost, solution, schedule = candidates[0]
            if cost + 1e-6 < best_cost or not best_solution.feasible:
                best_cost = cost
                best_solution = solution
                best_schedule = schedule
                best_route = list(solution.route)

        best_schedule.optimized = len(charge_indices) > 0
        return best_solution, best_schedule

    def _estimate_soc_at_node(
        self,
        solver: VRPSolver,
        route: list[str],
        node_idx: int,
        initial_soc: float,
    ) -> float:
        partial = route[: node_idx + 1]
        if len(partial) < 2:
            return initial_soc
        partial_route = partial + [partial[-1]]
        evaluation = solver._evaluate_schedule(partial_route, initial_soc)
        if evaluation.legs:
            return evaluation.legs[-1].soc_after
        return initial_soc

    def _simulate_with_charge_at(
        self,
        solver: VRPSolver,
        route: list[str],
        charge_idx: int,
        initial_soc: float,
        target_soc_after_charge: float,
        battery_capacity_kwh: float,
    ) -> RouteSolution:
        """模拟路线，在指定充电站充至 target_soc_after_charge。"""
        evaluation = solver._evaluate_schedule(route, initial_soc)
        if not evaluation.feasible and charge_idx >= len(route):
            return evaluation

        current_time = 0.0
        current_soc = initial_soc
        legs: list[RouteLeg] = []
        feasible = True
        violation = ""

        for i in range(len(route) - 1):
            from_id, to_id = route[i], route[i + 1]
            from_node = solver.nodes[from_id]
            to_node = solver.nodes[to_id]
            dist = solver._distance(from_id, to_id)
            travel_min = travel_time_minutes(dist, solver.speed_kmh)
            energy = solver.energy.compute_energy(dist, solver.speed_kmh)
            soc_drop = solver.energy.soc_consumption(energy, battery_capacity_kwh)

            arrival = current_time + travel_min
            wait = max(0.0, to_node.tw_start - arrival)
            start_service = arrival + wait

            if start_service > to_node.tw_end + 1e-6:
                feasible = False
                violation = f"节点 {to_id} 违反时间窗"

            soc_before = current_soc
            current_soc -= soc_drop
            if current_soc < solver.vparams.soc_min - 1e-6:
                feasible = False
                violation = f"路段 {from_id}->{to_id} SOC 不足"

            charge_kwh = 0.0
            charge_time = 0.0
            if to_id == route[charge_idx] and to_node.node_type == "charge":
                if current_soc < target_soc_after_charge - 1e-6:
                    charge_kwh = max(0.0, (target_soc_after_charge - current_soc) * battery_capacity_kwh)
                    charge_time = charge_kwh / max(to_node.charge_power_kw, 1.0) * 60.0
                    current_soc = target_soc_after_charge
            elif to_node.node_type == "charge" and current_soc < solver.vparams.charge_target_soc:
                target = solver.vparams.charge_target_soc
                charge_kwh = max(0.0, (target - current_soc) * battery_capacity_kwh)
                charge_time = charge_kwh / max(to_node.charge_power_kw, 1.0) * 60.0
                current_soc = target

            queue_wait = self._queue_wait_min(to_node) if to_node.node_type == "charge" else 0.0
            depart_time = start_service + to_node.service_time + charge_time + queue_wait

            legs.append(RouteLeg(
                from_node=from_id,
                to_node=to_id,
                distance_km=round(dist, 3),
                travel_time_min=round(travel_min, 2),
                energy_kwh=round(energy, 4),
                soc_before=round(soc_before, 4),
                soc_after=round(current_soc, 4),
                arrival_time=round(arrival, 2),
                wait_time_min=round(wait, 2),
                charge_kwh=round(charge_kwh, 4),
                charge_time_min=round(charge_time, 2),
            ))
            current_time = depart_time

        soc_trajectory = [{"node_id": route[0], "soc": round(initial_soc, 4), "time_min": 0.0}]
        t = 0.0
        for leg in legs:
            t += leg.travel_time_min + leg.wait_time_min + leg.charge_time_min
            soc_trajectory.append({
                "node_id": leg.to_node,
                "soc": leg.soc_after,
                "time_min": round(t, 2),
            })

        return RouteSolution(
            route=list(route),
            legs=legs,
            total_distance_km=round(solver._route_distance(route), 3),
            total_time_min=round(current_time, 2),
            total_energy_kwh=round(sum(l.energy_kwh for l in legs), 4),
            feasible=feasible,
            violation=violation,
            soc_trajectory=soc_trajectory,
        )

    def plan(
        self,
        route: list[str],
        legs: list[dict],
        nodes: dict[str, RouteNode] | None = None,
        node_meta: dict[str, dict] | None = None,
        battery_capacity_kwh: float = 100.0,
        initial_soc: float = 0.9,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
        optimize: bool = True,
    ) -> dict:
        """
        充电调度主入口：接收路径规划结果，输出 ChargePlan 及成本。

        可直接传入 legs 字典列表（来自路径 API），或传入 nodes 进行充电量优化。
        """
        if nodes is None:
            nodes = {}
            if node_meta:
                for nid, meta in node_meta.items():
                    nodes[nid] = RouteNode(
                        node_id=nid,
                        x=meta.get("x", 0.0),
                        y=meta.get("y", 0.0),
                        node_type=meta.get("type", "task"),
                        charge_power_kw=meta.get("charge_power_kw", 60.0),
                        charge_price=meta.get("charge_price", self.params.default_charge_price),
                        queue=meta.get("queue", 0),
                        tw_start=meta.get("tw_start", 0.0),
                        tw_end=meta.get("tw_end", 1440.0),
                        service_time=meta.get("service_time", 0.0),
                    )

        route_legs = [
            RouteLeg(
                from_node=leg["from"],
                to_node=leg["to"],
                distance_km=leg.get("distance_km", 0.0),
                travel_time_min=leg.get("travel_time_min", 0.0),
                energy_kwh=leg.get("energy_kwh", 0.0),
                soc_before=leg.get("soc_before", 0.0),
                soc_after=leg.get("soc_after", 0.0),
                arrival_time=leg.get("arrival_time", 0.0),
                wait_time_min=leg.get("wait_time_min", 0.0),
                charge_kwh=leg.get("charge_kwh", 0.0),
                charge_time_min=leg.get("charge_time_min", 0.0),
            )
            for leg in legs
        ]
        solution = RouteSolution(route=list(route), legs=route_legs)

        if optimize and nodes and any(
            nodes.get(n) and nodes[n].node_type == "charge" for n in route
        ):
            solution, schedule = self.optimize_charging(
                route=route,
                nodes=nodes,
                battery_capacity_kwh=battery_capacity_kwh,
                initial_soc=initial_soc,
                speed_kmh=speed_kmh,
                temperature=temperature,
            )
        else:
            schedule = self.extract_plans(solution, nodes)

        return self._to_dict(schedule, solution)

    @staticmethod
    def _to_dict(schedule: ChargeScheduleResult, solution: RouteSolution) -> dict:
        return {
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
            "refined_legs": [
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
            "soc_trajectory": solution.soc_trajectory,
        }
