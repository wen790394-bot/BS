"""强化学习环境：状态 S = {Position, SOC, Task, ...}, 动作 A = {NextNode, Charge}"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.services.energy.consumption import EnergyConsumptionService
from app.services.energy.vehicle_params import DEFAULT_VEHICLE_PARAMS
from app.services.routing.location import RouteNode, euclidean_distance, travel_time_minutes


@dataclass
class EnvConfig:
    nodes: dict[str, RouteNode]
    depot_id: str
    task_ids: list[str]
    charge_ids: list[str]
    battery_capacity_kwh: float = 60.0
    initial_soc: float = 0.25
    soh: float = 0.95
    speed_kmh: float = 40.0
    temperature: float = 25.0
    map_scale: float = 20.0


@dataclass
class StepRecord:
    state_vec: list[float]
    action_node: str
    reward: float
    done: bool
    log_prob: float = 0.0
    value: float = 0.0


class SchedulingEnv:
    """序贯决策环境：逐步选择下一访问节点，联合路径与充电决策。"""

    STATE_DIM = 12

    def __init__(self, config: EnvConfig):
        self.config = config
        self.energy = EnergyConsumptionService()
        self.vparams = DEFAULT_VEHICLE_PARAMS
        self.nodes = config.nodes
        self.depot_id = config.depot_id
        self.task_ids = list(config.task_ids)
        self.charge_ids = list(config.charge_ids)
        self.battery_capacity_kwh = config.battery_capacity_kwh
        self.initial_soc = config.initial_soc
        self.soh = config.soh
        self.speed_kmh = config.speed_kmh
        self.temperature = config.temperature
        self.map_scale = config.map_scale

        self.current_node: str = config.depot_id
        self.soc: float = config.initial_soc
        self.time_min: float = 0.0
        self.visited_tasks: set[str] = set()
        self.route: list[str] = [config.depot_id]
        self.history: list[dict] = []
        self.state_sequence: list[list[float]] = []
        self.step_records: list[StepRecord] = []
        self.total_reward: float = 0.0
        self.done: bool = False
        self._prev_soc: float = config.initial_soc

    def reset(self) -> dict:
        self.current_node = self.depot_id
        self.soc = self.initial_soc
        self.time_min = 0.0
        self.visited_tasks = set()
        self.route = [self.depot_id]
        self.history = []
        self.state_sequence = []
        self.step_records = []
        self.total_reward = 0.0
        self.done = False
        self._prev_soc = self.initial_soc
        state = self._build_state()
        self.state_sequence.append(state["vector"])
        return state

    def _node(self, node_id: str) -> RouteNode:
        return self.nodes[node_id]

    def _normalize_pos(self, node: RouteNode) -> tuple[float, float]:
        return node.x / self.map_scale, node.y / self.map_scale

    def _travel_cost(self, from_id: str, to_id: str) -> tuple[float, float, float]:
        dist = euclidean_distance(self._node(from_id), self._node(to_id))
        travel_min = travel_time_minutes(dist, self.speed_kmh)
        energy = self.energy.compute_energy(dist, self.speed_kmh)
        return dist, travel_min, energy

    def _remaining_tasks(self) -> list[str]:
        return [t for t in self.task_ids if t not in self.visited_tasks]

    def _nearest_task_distance(self) -> float:
        remaining = self._remaining_tasks()
        if not remaining:
            return 0.0
        cur = self._node(self.current_node)
        return min(euclidean_distance(cur, self._node(t)) for t in remaining) / self.map_scale

    def _avg_charge_price(self) -> float:
        if not self.charge_ids:
            return 1.2
        return sum(self._node(s).charge_price for s in self.charge_ids) / len(self.charge_ids) / 2.0

    def _avg_queue(self) -> float:
        if not self.charge_ids:
            return 0.0
        return sum(self._node(s).queue for s in self.charge_ids) / max(len(self.charge_ids), 1) / 5.0

    def _build_state(self) -> dict:
        node = self._node(self.current_node)
        px, py = self._normalize_pos(node)
        remaining = self._remaining_tasks()
        unvisited_ratio = len(remaining) / max(len(self.task_ids), 1)
        delta_soc = self.soc - self._prev_soc
        at_charge = 1.0 if node.node_type == "charge" else 0.0
        traffic = min(1.0, self.time_min / 720.0)

        vector = [
            px,
            py,
            self.soc,
            self.soh,
            self.time_min / 1440.0,
            delta_soc,
            unvisited_ratio,
            at_charge,
            self._nearest_task_distance(),
            traffic,
            self._avg_charge_price(),
            self._avg_queue(),
        ]

        return {
            "position": {"x": node.x, "y": node.y, "node_id": self.current_node},
            "soc": round(self.soc, 4),
            "soh": self.soh,
            "time_min": round(self.time_min, 2),
            "unvisited_tasks": remaining,
            "visited_tasks": list(self.visited_tasks),
            "route": list(self.route),
            "vector": vector,
            "feasible_actions": self.get_feasible_actions(),
        }

    def get_feasible_actions(self) -> list[str]:
        if self.done:
            return []

        actions: list[str] = []
        remaining = self._remaining_tasks()
        cur = self._node(self.current_node)

        for task_id in remaining:
            if task_id not in self.route and self._can_reach(self.current_node, task_id):
                actions.append(task_id)

        if self.soc < self.vparams.charge_target_soc - 0.05 and self.charge_ids:
            for station_id in self.charge_ids:
                if (
                    station_id != self.current_node
                    and station_id not in self.route
                    and self._can_reach(self.current_node, station_id)
                ):
                    actions.append(station_id)

        if not remaining:
            if self._can_reach(self.current_node, self.depot_id):
                actions.append(self.depot_id)
        elif self.soc < self.vparams.soc_min + 0.15 and self.charge_ids:
            for station_id in self.charge_ids:
                if (
                    station_id not in actions
                    and station_id != self.current_node
                    and station_id not in self.route
                ):
                    if self._can_reach(self.current_node, station_id):
                        actions.append(station_id)

        if not actions and remaining:
            nearest = min(
                remaining,
                key=lambda t: euclidean_distance(cur, self._node(t)),
            )
            actions.append(nearest)

        if not actions:
            actions.append(self.depot_id)

        return list(dict.fromkeys(actions))

    def _can_reach(self, from_id: str, to_id: str) -> bool:
        _, travel_min, energy = self._travel_cost(from_id, to_id)
        soc_need = self.energy.soc_consumption(energy, self.battery_capacity_kwh)
        arrival = self.time_min + travel_min
        to_node = self._node(to_id)

        if self.soc - soc_need < self.vparams.soc_min - 1e-6:
            if to_node.node_type != "charge":
                return False

        if to_node.node_type == "task" and to_id in self.task_ids:
            wait = max(0.0, to_node.tw_start - arrival)
            start_service = arrival + wait
            if start_service > to_node.tw_end + 1e-6:
                return False

        return True

    def _step_cost(self, dist: float, energy: float, wait_min: float, charge_kwh: float, price: float) -> float:
        vp = self.vparams
        c_travel = dist * vp.cost_per_km
        c_energy = energy * vp.electricity_price
        c_charge = charge_kwh * price
        c_waiting = wait_min * 0.5
        return c_travel + c_energy + c_charge + c_waiting

    def step(self, action: dict) -> tuple[dict, float, bool, dict]:
        if self.done:
            return self._build_state(), 0.0, True, {"violation": "episode已结束"}

        next_node = action.get("next_node")
        if not next_node or next_node not in self.nodes:
            return self._build_state(), -50.0, True, {"violation": "无效动作"}

        charge_target_soc = action.get("charge_target_soc")
        if charge_target_soc is None:
            charge_amount = action.get("charge_amount", 0.0)
            if charge_amount > 0:
                charge_target_soc = min(
                    self.vparams.charge_target_soc,
                    self.soc + charge_amount / self.battery_capacity_kwh,
                )
            elif action.get("charge"):
                charge_target_soc = self.vparams.charge_target_soc

        dist, travel_min, energy = self._travel_cost(self.current_node, next_node)
        arrival = self.time_min + travel_min
        to_node = self._node(next_node)
        wait = max(0.0, to_node.tw_start - arrival)
        start_service = arrival + wait

        violation = ""
        penalty = 0.0
        if to_node.node_type == "task" and start_service > to_node.tw_end + 1e-6:
            violation = f"违反时间窗: {next_node}"
            penalty += 30.0

        self._prev_soc = self.soc
        soc_drop = self.energy.soc_consumption(energy, self.battery_capacity_kwh)
        self.soc -= soc_drop
        if self.soc < self.vparams.soc_min - 1e-6 and to_node.node_type != "charge":
            violation = violation or f"SOC 不足: {self.soc:.3f}"
            penalty += 40.0

        charge_kwh = 0.0
        charge_time = 0.0
        price = to_node.charge_price if to_node.node_type == "charge" else 0.0

        if to_node.node_type == "charge":
            target = charge_target_soc if charge_target_soc is not None else self.vparams.charge_target_soc
            target = min(max(target, self.soc), self.vparams.charge_target_soc)
            if target > self.soc + 1e-6:
                charge_kwh = (target - self.soc) * self.battery_capacity_kwh
                charge_time = charge_kwh / max(to_node.charge_power_kw, 1.0) * 60.0
                self.soc = target

        queue_wait = to_node.queue * 5.0 if to_node.node_type == "charge" else 0.0
        step_cost = self._step_cost(dist, energy, wait + queue_wait, charge_kwh, price)
        reward = -step_cost - penalty

        if next_node in self.route[1:] and next_node != self.depot_id:
            penalty += 25.0
            violation = violation or f"重复访问: {next_node}"

        if next_node in self.task_ids:
            self.visited_tasks.add(next_node)

        depart_time = start_service + to_node.service_time + charge_time + queue_wait
        self.time_min = depart_time
        self.current_node = next_node
        self.route.append(next_node)

        self.history.append({
            "from": self.route[-2] if len(self.route) > 1 else self.depot_id,
            "to": next_node,
            "distance_km": round(dist, 3),
            "energy_kwh": round(energy, 4),
            "soc": round(self.soc, 4),
            "charge_kwh": round(charge_kwh, 4),
            "step_cost": round(step_cost, 2),
        })

        remaining = self._remaining_tasks()
        self.done = next_node == self.depot_id and not remaining
        if not remaining and next_node != self.depot_id and len(self.route) > len(self.task_ids) + 3:
            self.done = True

        if not self.done and not remaining and next_node != self.depot_id:
            pass
        elif not remaining and next_node != self.depot_id:
            pass

        if not remaining and next_node == self.depot_id:
            self.done = True
            if not violation:
                reward += 20.0

        if self.done and remaining:
            reward -= 50.0 * len(remaining)
            violation = violation or f"未完成订单: {remaining}"

        state = self._build_state()
        self.state_sequence.append(state["vector"])
        self.total_reward += reward

        info = {
            "step_cost": round(step_cost, 2),
            "penalty": penalty,
            "violation": violation,
            "route": list(self.route),
        }
        return state, reward, self.done, info

    def build_complete_route(self) -> list[str]:
        """确保返回闭合路线。"""
        route = list(self.route)
        remaining = self._remaining_tasks()
        for task_id in remaining:
            route.append(task_id)
        if route[-1] != self.depot_id:
            route.append(self.depot_id)
        return route

    @staticmethod
    def demo_config(
        battery_capacity_kwh: float = 60.0,
        initial_soc: float = 0.25,
        soh: float = 0.95,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
    ) -> EnvConfig:
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
        nodes = {depot.node_id: depot}
        for node in tasks + stations:
            nodes[node.node_id] = node
        return EnvConfig(
            nodes=nodes,
            depot_id="depot",
            task_ids=[t.node_id for t in tasks],
            charge_ids=[s.node_id for s in stations],
            battery_capacity_kwh=battery_capacity_kwh,
            initial_soc=initial_soc,
            soh=soh,
            speed_kmh=speed_kmh,
            temperature=temperature,
        )
