"""
电动物流车路径优化求解器 (EVRPTW)。

算法: 最优插入法构造初始解 + 2-opt 局部搜索 + 电量不可行时插入充电站。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.services.energy.consumption import EnergyConsumptionService
from app.services.energy.vehicle_params import DEFAULT_VEHICLE_PARAMS, VehicleDynamicsParams
from app.services.routing.location import RouteNode, euclidean_distance, travel_time_minutes


@dataclass
class RouteLeg:
    from_node: str
    to_node: str
    distance_km: float
    travel_time_min: float
    energy_kwh: float
    soc_before: float
    soc_after: float
    arrival_time: float
    wait_time_min: float = 0.0
    charge_kwh: float = 0.0
    charge_time_min: float = 0.0


@dataclass
class RouteSolution:
    route: list[str]
    legs: list[RouteLeg] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_min: float = 0.0
    total_energy_kwh: float = 0.0
    feasible: bool = True
    violation: str = ""
    arrival_times: dict[str, float] = field(default_factory=dict)
    soc_trajectory: list[dict] = field(default_factory=list)


class VRPSolver:
    def __init__(
        self,
        nodes: dict[str, RouteNode],
        depot_id: str,
        energy_service: EnergyConsumptionService | None = None,
        vehicle_params: VehicleDynamicsParams | None = None,
        battery_capacity_kwh: float = 100.0,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
    ):
        self.nodes = nodes
        self.depot_id = depot_id
        self.energy = energy_service or EnergyConsumptionService()
        self.vparams = vehicle_params or DEFAULT_VEHICLE_PARAMS
        self.battery_capacity_kwh = battery_capacity_kwh
        self.speed_kmh = speed_kmh
        self.temperature = temperature
        self._dist_cache: dict[tuple[str, str], float] = {}

    def _distance(self, a_id: str, b_id: str) -> float:
        key = (a_id, b_id)
        if key not in self._dist_cache:
            self._dist_cache[key] = euclidean_distance(self.nodes[a_id], self.nodes[b_id])
        return self._dist_cache[key]

    def _route_distance(self, route: list[str]) -> float:
        return sum(self._distance(route[i], route[i + 1]) for i in range(len(route) - 1))

    def _evaluate_schedule(self, route: list[str], initial_soc: float) -> RouteSolution:
        """模拟路线执行，检查时间窗与 SOC 约束。"""
        solution = RouteSolution(route=list(route))
        current_time = 0.0
        current_soc = initial_soc
        total_energy = 0.0

        solution.soc_trajectory.append({
            "node_id": route[0],
            "soc": round(current_soc, 4),
            "time_min": 0.0,
        })

        for i in range(len(route) - 1):
            from_id, to_id = route[i], route[i + 1]
            dist = self._distance(from_id, to_id)
            travel_min = travel_time_minutes(dist, self.speed_kmh)
            energy = self.energy.compute_energy(dist, self.speed_kmh)
            soc_drop = self.energy.soc_consumption(energy, self.battery_capacity_kwh)

            arrival = current_time + travel_min
            to_node = self.nodes[to_id]
            wait = max(0.0, to_node.tw_start - arrival)
            start_service = arrival + wait

            if start_service > to_node.tw_end + 1e-6:
                solution.feasible = False
                solution.violation = (
                    f"节点 {to_id} 违反时间窗 (到达 {start_service:.1f} > {to_node.tw_end})"
                )

            soc_before = current_soc
            current_soc -= soc_drop
            if current_soc < self.vparams.soc_min - 1e-6:
                solution.feasible = False
                solution.violation = (
                    f"路段 {from_id}->{to_id} SOC 不足 ({current_soc:.3f} < {self.vparams.soc_min})"
                )

            charge_kwh = 0.0
            charge_time = 0.0
            if to_node.node_type == "charge" and current_soc < self.vparams.charge_target_soc:
                target_energy = (self.vparams.charge_target_soc - current_soc) * self.battery_capacity_kwh
                charge_kwh = max(0.0, target_energy)
                charge_time = charge_kwh / max(to_node.charge_power_kw, 1.0) * 60.0
                current_soc = self.vparams.charge_target_soc

            depart_time = start_service + to_node.service_time + charge_time
            solution.legs.append(RouteLeg(
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
            solution.arrival_times[to_id] = round(start_service, 2)
            solution.soc_trajectory.append({
                "node_id": to_id,
                "soc": round(current_soc, 4),
                "time_min": round(depart_time, 2),
            })

            current_time = depart_time
            total_energy += energy

        solution.total_distance_km = round(self._route_distance(route), 3)
        solution.total_time_min = round(current_time, 2)
        solution.total_energy_kwh = round(total_energy, 4)
        return solution

    def _insertion_cost(self, route: list[str], node_id: str, pos: int) -> float:
        prev_id = route[pos - 1]
        next_id = route[pos]
        before = self._distance(prev_id, next_id)
        after = self._distance(prev_id, node_id) + self._distance(node_id, next_id)
        return after - before

    def _build_initial_route(self, task_ids: list[str], charge_ids: list[str], initial_soc: float) -> list[str]:
        """最优插入法构造初始路线。"""
        route = [self.depot_id, self.depot_id]
        unvisited = list(task_ids)

        while unvisited:
            best: tuple[str, int, float] | None = None
            for task_id in unvisited:
                for pos in range(1, len(route)):
                    trial = route[:pos] + [task_id] + route[pos:]
                    eval_result = self._evaluate_schedule(trial, initial_soc)
                    if eval_result.feasible:
                        cost = self._insertion_cost(route, task_id, pos)
                        if best is None or cost < best[2]:
                            best = (task_id, pos, cost)

            if best is None:
                break

            task_id, pos, _ = best
            route.insert(pos, task_id)
            unvisited.remove(task_id)

        if unvisited and charge_ids:
            route = self._insert_charging_stations(route, charge_ids, initial_soc)

        return route

    def _insert_charging_stations(
        self,
        route: list[str],
        charge_ids: list[str],
        initial_soc: float,
    ) -> list[str]:
        """电量不可行时，贪心插入最近充电站。"""
        improved = list(route)
        for _ in range(3):
            evaluation = self._evaluate_schedule(improved, initial_soc)
            if evaluation.feasible:
                return improved

            best_route: list[str] | None = None
            violation_leg = next(
                (leg for leg in evaluation.legs if leg.soc_after < self.vparams.soc_min),
                evaluation.legs[0] if evaluation.legs else None,
            )
            if violation_leg is None:
                break

            from_idx = improved.index(violation_leg.from_node)
            insert_pos = from_idx + 1
            for station_id in charge_ids:
                trial = improved[:insert_pos] + [station_id] + improved[insert_pos:]
                if self._evaluate_schedule(trial, initial_soc).feasible:
                    best_route = trial
                    break

            if best_route is None:
                station_id = min(
                    charge_ids,
                    key=lambda s: self._distance(violation_leg.from_node, s),
                ) if charge_ids else None
                if station_id:
                    improved = improved[:insert_pos] + [station_id] + improved[insert_pos:]
                else:
                    break
            else:
                improved = best_route

        return improved

    def _two_opt(self, route: list[str], initial_soc: float, max_iter: int = 100) -> list[str]:
        """2-opt 局部搜索，保持首尾为仓库。"""
        if len(route) <= 4:
            return route

        best = list(route)
        best_cost = self._route_distance(best)
        improved = True
        iteration = 0

        while improved and iteration < max_iter:
            improved = False
            iteration += 1
            for i in range(1, len(best) - 2):
                for j in range(i + 1, len(best) - 1):
                    if j - i == 1:
                        continue
                    candidate = best[:i] + best[i:j][::-1] + best[j:]
                    if candidate[0] != self.depot_id or candidate[-1] != self.depot_id:
                        continue
                    evaluation = self._evaluate_schedule(candidate, initial_soc)
                    if not evaluation.feasible:
                        continue
                    cost = self._route_distance(candidate)
                    if cost + 1e-6 < best_cost:
                        best = candidate
                        best_cost = cost
                        improved = True
        return best

    def _alns_improve(self, route: list[str], task_ids: list[str], initial_soc: float, iterations: int = 50) -> list[str]:
        """简化 ALNS：随机移除后重新插入。"""
        best = list(route)
        best_eval = self._evaluate_schedule(best, initial_soc)
        if not best_eval.feasible:
            return best

        best_cost = best_eval.total_distance_km
        current = list(best)

        for _ in range(iterations):
            if len(current) <= 3:
                break
            inner_tasks = [n for n in current[1:-1] if n in task_ids]
            if len(inner_tasks) < 2:
                break

            remove_count = max(1, int(len(inner_tasks) * random.uniform(0.2, 0.4)))
            removed = random.sample(inner_tasks, min(remove_count, len(inner_tasks)))
            working = [n for n in current if n not in removed]

            for task_id in removed:
                best_insert: tuple[int, float] | None = None
                for pos in range(1, len(working)):
                    trial = working[:pos] + [task_id] + working[pos:]
                    ev = self._evaluate_schedule(trial, initial_soc)
                    if ev.feasible:
                        cost = self._route_distance(trial)
                        if best_insert is None or cost < best_insert[1]:
                            best_insert = (pos, cost)
                if best_insert:
                    pos, _ = best_insert
                    working = working[:pos] + [task_id] + working[pos:]

            working = self._two_opt(working, initial_soc, max_iter=20)
            ev = self._evaluate_schedule(working, initial_soc)
            if ev.feasible and ev.total_distance_km + 1e-6 < best_cost:
                best = working
                best_cost = ev.total_distance_km
                current = working
            else:
                current = working if self._evaluate_schedule(working, initial_soc).feasible else current

        return best

    def solve(
        self,
        task_ids: list[str],
        charge_ids: list[str] | None = None,
        initial_soc: float = 1.0,
        method: str = "insertion_2opt",
    ) -> RouteSolution:
        """求解单车辆路径，目标最小化行驶距离，满足时间窗与 SOC 约束。"""
        charge_ids = charge_ids or []
        task_ids = [t for t in task_ids if t in self.nodes and t != self.depot_id]

        if not task_ids:
            route = [self.depot_id, self.depot_id]
            return self._evaluate_schedule(route, initial_soc)

        route = self._build_initial_route(task_ids, charge_ids, initial_soc)
        evaluation = self._evaluate_schedule(route, initial_soc)

        if not evaluation.feasible and charge_ids:
            route = self._insert_charging_stations(route, charge_ids, initial_soc)

        if method in ("insertion_2opt", "alns", "mamba_ppo", "ppo", "transformer_ppo"):
            route = self._two_opt(route, initial_soc)

        if method == "alns":
            route = self._alns_improve(route, task_ids, initial_soc)

        if not self._evaluate_schedule(route, initial_soc).feasible and charge_ids:
            route = self._insert_charging_stations(route, charge_ids, initial_soc)
            route = self._two_opt(route, initial_soc, max_iter=30)

        return self._evaluate_schedule(route, initial_soc)
