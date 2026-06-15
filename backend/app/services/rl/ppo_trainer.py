"""PPO 策略优化 + Mamba-PPO 联合路径与充电推理（PyTorch GPU / NumPy 双模式）。"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ChargeStation, TaskInfo, VehicleInfo
from app.services.energy.consumption import EnergyConsumptionService
from app.services.routing.location import RouteNode, parse_location
from app.services.routing.path_planner import PathPlanner
from app.services.routing.vrp_solver import VRPSolver
from app.services.rl.actor_critic import NumpyActorCritic, TorchActorCritic, create_actor_critic
from app.services.rl.device import device_info, get_torch_device
from app.services.rl.env import EnvConfig, SchedulingEnv
from app.services.scheduling.charge_scheduler import ChargeScheduler


@dataclass
class RolloutBuffer:
    states: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)
    log_probs: list[float] = field(default_factory=list)
    values: list[float] = field(default_factory=list)


class PPOTrainer:
    """Mamba-PPO / Transformer-PPO / PPO 训练与推理。"""

    def __init__(self):
        self.path_planner = PathPlanner()
        self.charge_scheduler = ChargeScheduler()
        self.energy = EnergyConsumptionService()
        self._policies: dict[str, Any] = {}
        self._optimizers: dict[str, torch.optim.Adam] = {}
        self._trained: dict[str, bool] = {}
        self._use_torch = settings.rl_backend != "numpy"

    def _get_policy(self, algorithm: str):
        if algorithm not in self._policies:
            self._policies[algorithm] = create_actor_critic(algorithm)
            if self._use_torch and isinstance(self._policies[algorithm], TorchActorCritic):
                self._optimizers[algorithm] = torch.optim.Adam(
                    self._policies[algorithm].parameters(),
                    lr=settings.ppo_lr,
                )
            self._bootstrap_policy(algorithm)
        return self._policies[algorithm]

    def _bootstrap_policy(self, algorithm: str, episodes: int | None = None) -> None:
        if self._trained.get(algorithm):
            return
        episodes = episodes or settings.bootstrap_episodes
        policy = self._policies[algorithm]
        config = SchedulingEnv.demo_config()
        for ep in range(episodes):
            env = SchedulingEnv(config)
            buffer = self._run_episode(env, policy, deterministic=False)
            if buffer.rewards:
                lr = 0.02 if ep < 20 else 0.008
                if self._use_torch and isinstance(policy, TorchActorCritic):
                    self._ppo_update_torch(policy, self._optimizers[algorithm], buffer)
                else:
                    self._ppo_update_numpy(policy, buffer, lr=lr)
        self._trained[algorithm] = True

    def _enrich_state(self, env: SchedulingEnv, state: dict) -> dict:
        enriched = copy.copy(state)
        enriched["state_sequence"] = list(env.state_sequence)
        enriched["nodes"] = env.nodes
        enriched["battery_capacity_kwh"] = env.battery_capacity_kwh
        return enriched

    def _run_episode(
        self,
        env: SchedulingEnv,
        policy: Any,
        deterministic: bool = False,
        max_steps: int = 30,
    ) -> RolloutBuffer:
        buffer = RolloutBuffer()
        state = env.reset()
        steps = 0

        while not env.done and steps < max_steps:
            enriched = self._enrich_state(env, state)
            action, value = policy.select_action_with_value(enriched, deterministic=deterministic)
            next_state, reward, done, _info = env.step(action)

            buffer.states.append(enriched)
            buffer.actions.append(action)
            buffer.rewards.append(reward)
            buffer.dones.append(done)
            buffer.log_probs.append(action.get("log_prob", 0.0))
            buffer.values.append(value)

            state = next_state
            steps += 1

            if not env._remaining_tasks() and env.current_node != env.depot_id:
                enriched = self._enrich_state(env, state)
                action, value = policy.select_action_with_value(enriched, deterministic=True)
                if action["next_node"] == env.depot_id:
                    next_state, reward, done, _ = env.step(action)
                    buffer.states.append(enriched)
                    buffer.actions.append(action)
                    buffer.rewards.append(reward)
                    buffer.dones.append(done)
                    buffer.log_probs.append(action.get("log_prob", 0.0))
                    buffer.values.append(value)
                    state = next_state
                else:
                    depot_action = {"next_node": env.depot_id, "charge": False, "charge_amount": 0.0}
                    next_state, reward, done, _ = env.step(depot_action)
                    buffer.rewards[-1] += reward
                    buffer.dones[-1] = done
                break

        return buffer

    def _compute_gae(
        self,
        rewards: list[float],
        values: list[float],
        dones: list[bool],
        gamma: float | None = None,
        lam: float | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        gamma = gamma or settings.ppo_gamma
        lam = lam or settings.ppo_gae_lambda
        n = len(rewards)
        advantages = np.zeros(n)
        returns = np.zeros(n)
        gae = 0.0
        next_value = 0.0

        for t in reversed(range(n)):
            mask = 0.0 if dones[t] else 1.0
            delta = rewards[t] + gamma * next_value * mask - values[t]
            gae = delta + gamma * lam * mask * gae
            advantages[t] = gae
            returns[t] = advantages[t] + values[t]
            next_value = values[t]

        if n > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        return advantages, returns

    def _ppo_update_torch(
        self,
        policy: TorchActorCritic,
        optimizer: torch.optim.Adam,
        buffer: RolloutBuffer,
    ) -> dict:
        if not buffer.rewards:
            return {"loss": 0.0}

        advantages, returns = self._compute_gae(buffer.rewards, buffer.values, buffer.dones)
        policy.train()
        actor_loss_total = 0.0
        critic_loss_total = 0.0
        count = 0

        for i, state in enumerate(buffer.states):
            action = buffer.actions[i]
            candidates = action.get("candidates") or state.get("feasible_actions") or []
            if not candidates:
                continue

            logits, _ = policy.score_candidates(state, candidates)
            probs = F.softmax(logits, dim=0)
            idx = min(action.get("action_idx", 0), len(candidates) - 1)

            new_log_prob = torch.log(probs[idx] + 1e-8)
            old_log_prob = torch.tensor(buffer.log_probs[i], device=logits.device)
            ratio = torch.exp(new_log_prob - old_log_prob)
            adv = torch.tensor(advantages[i], device=logits.device)

            surr1 = ratio * adv
            surr2 = torch.clamp(ratio, 1.0 - settings.ppo_clip_eps, 1.0 + settings.ppo_clip_eps) * adv
            actor_loss = -torch.min(surr1, surr2)

            value = policy.evaluate(state)
            ret = torch.tensor(returns[i], device=value.device)
            critic_loss = 0.5 * (value - ret) ** 2

            loss = actor_loss + critic_loss
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
            optimizer.step()

            actor_loss_total += float(actor_loss.item())
            critic_loss_total += float(critic_loss.item())
            count += 1

        policy.eval()
        return {
            "actor_loss": actor_loss_total / max(count, 1),
            "critic_loss": critic_loss_total / max(count, 1),
        }

    def _ppo_update_numpy(
        self,
        policy: NumpyActorCritic,
        buffer: RolloutBuffer,
        lr: float = 0.01,
        clip_eps: float | None = None,
    ) -> dict:
        clip_eps = clip_eps or settings.ppo_clip_eps
        if not buffer.rewards:
            return {"loss": 0.0}

        advantages, returns = self._compute_gae(buffer.rewards, buffer.values, buffer.dones)
        actor_loss_total = 0.0
        critic_loss_total = 0.0
        count = 0

        for i, state in enumerate(buffer.states):
            action = buffer.actions[i]
            candidates = action.get("candidates") or state.get("feasible_actions") or []
            if not candidates:
                continue

            logits, embedding = policy._score_candidates(state, candidates)
            probs = np.exp(logits - np.max(logits))
            probs = probs / (np.sum(probs) + 1e-8)
            idx = action.get("action_idx", int(np.argmax(probs)))
            idx = min(idx, len(candidates) - 1)

            new_log_prob = float(np.log(probs[idx] + 1e-8))
            old_log_prob = buffer.log_probs[i]
            ratio = np.exp(new_log_prob - old_log_prob)
            adv = advantages[i]

            surr1 = ratio * adv
            surr2 = np.clip(ratio, 1.0 - clip_eps, 1.0 + clip_eps) * adv
            actor_loss = -min(surr1, surr2)

            value = policy.evaluate(state)
            critic_loss = 0.5 * (value - returns[i]) ** 2

            grad_scale = lr * actor_loss
            feat = policy._action_features(state, candidates[idx])
            x = np.concatenate([embedding, feat])
            h = np.tanh(x @ policy.W_actor + policy.b_actor)

            policy.W_actor_out[:, 0] -= grad_scale * 0.01 * h
            policy.W_actor -= grad_scale * 0.001 * np.outer(x, h) * (1 - h ** 2)

            critic_grad = lr * (value - returns[i])
            h_c = np.tanh(embedding @ policy.W_critic + policy.b_critic)
            policy.W_critic_out[:, 0] -= critic_grad * 0.01 * h_c
            policy.W_critic -= critic_grad * 0.001 * np.outer(embedding, h_c) * (1 - h_c ** 2)

            actor_loss_total += float(actor_loss)
            critic_loss_total += float(critic_loss)
            count += 1

        return {
            "actor_loss": actor_loss_total / max(count, 1),
            "critic_loss": critic_loss_total / max(count, 1),
        }

    def train(self, episodes: int = 200, algorithm: str = "mamba_ppo") -> dict:
        policy = self._get_policy(algorithm)
        config = SchedulingEnv.demo_config()
        losses: list[dict] = []

        for _ in range(episodes):
            env = SchedulingEnv(config)
            buffer = self._run_episode(env, policy, deterministic=False)
            if buffer.rewards:
                if self._use_torch and isinstance(policy, TorchActorCritic):
                    loss = self._ppo_update_torch(policy, self._optimizers[algorithm], buffer)
                else:
                    loss = self._ppo_update_numpy(policy, buffer)
                losses.append(loss)

        self._trained[algorithm] = True
        avg_actor = np.mean([l["actor_loss"] for l in losses]) if losses else 0.0
        avg_critic = np.mean([l["critic_loss"] for l in losses]) if losses else 0.0
        info = device_info()
        return {
            "status": "ok",
            "algorithm": algorithm,
            "episodes": episodes,
            "avg_actor_loss": round(float(avg_actor), 4),
            "avg_critic_loss": round(float(avg_critic), 4),
            "device": info["device"],
            "mamba_backend": info["mamba_backend"],
        }

    def _finalize_route(self, env: SchedulingEnv) -> list[str]:
        route = list(env.route)
        remaining = env._remaining_tasks()

        if remaining:
            cur = env.current_node
            while remaining:
                nearest = min(
                    remaining,
                    key=lambda t: (
                        (env.nodes[cur].x - env.nodes[t].x) ** 2
                        + (env.nodes[cur].y - env.nodes[t].y) ** 2
                    ) ** 0.5,
                )
                route.append(nearest)
                remaining.remove(nearest)
                cur = nearest

        if route[-1] != env.depot_id:
            route.append(env.depot_id)
        return route

    def _evaluate_route(self, config: EnvConfig, route: list[str], algorithm: str) -> dict:
        nodes = config.nodes
        solver = VRPSolver(
            nodes=nodes,
            depot_id=config.depot_id,
            energy_service=self.energy,
            battery_capacity_kwh=config.battery_capacity_kwh,
            speed_kmh=config.speed_kmh,
            temperature=config.temperature,
        )

        if config.charge_ids:
            solution, schedule = self.charge_scheduler.optimize_charging(
                route=route,
                nodes=nodes,
                battery_capacity_kwh=config.battery_capacity_kwh,
                initial_soc=config.initial_soc,
                speed_kmh=config.speed_kmh,
                temperature=config.temperature,
            )
        else:
            solution = solver._evaluate_schedule(route, config.initial_soc)
            schedule = self.charge_scheduler.extract_plans(solution, nodes)

        costs = self.path_planner._compute_costs(
            solution, nodes, config.soh, config.temperature,
        )

        all_node_ids = set(solution.route)
        node_positions = {
            nid: {"x": nodes[nid].x, "y": nodes[nid].y, "type": nodes[nid].node_type}
            for nid in all_node_ids if nid in nodes
        }

        return {
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
            "soc_trajectory": solution.soc_trajectory,
            "node_positions": node_positions,
            "algorithm": algorithm,
        }

    def _build_config_from_db(
        self,
        db: Session,
        vehicle_ids: list[str],
        task_ids: list[str],
    ) -> EnvConfig:
        if not vehicle_ids:
            raise ValueError("请提供 vehicle_ids")
        vehicle = db.get(VehicleInfo, vehicle_ids[0])
        if not vehicle:
            raise ValueError(f"车辆 {vehicle_ids[0]} 不存在")

        tasks_db = [db.get(TaskInfo, tid) for tid in task_ids]
        missing = [tid for tid, t in zip(task_ids, tasks_db) if t is None]
        if missing:
            raise ValueError(f"订单不存在: {missing}")

        depot_xy = parse_location(vehicle.location or "0,0")
        depot = RouteNode(
            node_id="depot",
            x=depot_xy[0],
            y=depot_xy[1],
            node_type="depot",
        )

        tasks: list[RouteNode] = []
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

        stations: list[RouteNode] = []
        for station in db.query(ChargeStation).all():
            xy = parse_location(station.location or "0,0")
            stations.append(RouteNode(
                node_id=station.station_id,
                x=xy[0],
                y=xy[1],
                node_type="charge",
                charge_power_kw=60.0,
                charge_price=station.price or 1.2,
                queue=station.queue or 0,
            ))

        nodes = {depot.node_id: depot}
        for node in tasks + stations:
            nodes[node.node_id] = node

        return EnvConfig(
            nodes=nodes,
            depot_id="depot",
            task_ids=[t.node_id for t in tasks],
            charge_ids=[s.node_id for s in stations],
            battery_capacity_kwh=vehicle.capacity,
            initial_soc=vehicle.soc,
            soh=vehicle.soh,
        )

    def infer(
        self,
        vehicle_ids: list[str] | None = None,
        task_ids: list[str] | None = None,
        algorithm: str = "mamba_ppo",
        use_demo: bool = True,
        db: Session | None = None,
        battery_capacity_kwh: float = 60.0,
        initial_soc: float = 0.25,
        soh: float = 0.95,
        speed_kmh: float = 40.0,
        temperature: float = 25.0,
        num_rollouts: int = 5,
    ) -> dict:
        start = time.perf_counter()
        policy = self._get_policy(algorithm)

        if use_demo or not vehicle_ids:
            config = SchedulingEnv.demo_config(
                battery_capacity_kwh=battery_capacity_kwh,
                initial_soc=initial_soc,
                soh=soh,
                speed_kmh=speed_kmh,
                temperature=temperature,
            )
            vehicle_ids = vehicle_ids or []
            task_ids = task_ids or config.task_ids
        elif db is not None:
            config = self._build_config_from_db(db, vehicle_ids, task_ids or [])
        else:
            raise ValueError("非演示模式需要提供数据库会话")

        best_result: dict | None = None
        best_cost = float("inf")

        for _ in range(num_rollouts):
            env = SchedulingEnv(config)
            self._run_episode(env, policy, deterministic=False)
            route = self._finalize_route(env)
            result = self._evaluate_route(config, route, algorithm)

            cost = result["cost_breakdown"]["total"]
            if result["feasible"] and cost < best_cost:
                best_cost = cost
                best_result = result

            if best_result is None or not best_result.get("feasible"):
                det_env = SchedulingEnv(config)
                self._run_episode(det_env, policy, deterministic=True)
                route = self._finalize_route(det_env)
                result = self._evaluate_route(config, route, algorithm)
                cost = result["cost_breakdown"]["total"]
                if cost < best_cost:
                    best_cost = cost
                    best_result = result

        if best_result is None:
            fallback = self.path_planner.demo_instance(
                battery_capacity_kwh=battery_capacity_kwh,
                initial_soc=initial_soc,
                soh=soh,
                speed_kmh=speed_kmh,
                temperature=temperature,
                method="insertion_2opt",
                optimize_charging=True,
            )
            best_result = {
                "route": fallback["route"],
                "feasible": fallback["feasible"],
                "violation": fallback.get("violation", ""),
                "total_distance_km": fallback["total_distance_km"],
                "total_time_min": fallback["total_time_min"],
                "total_energy_kwh": fallback["total_energy_kwh"],
                "cost_breakdown": fallback["cost_breakdown"],
                "charge_plan": fallback.get("charge_plan"),
                "legs": fallback.get("legs"),
                "soc_trajectory": fallback.get("soc_trajectory"),
                "node_positions": fallback.get("node_positions"),
                "algorithm": algorithm,
            }

        runtime = time.perf_counter() - start
        route_id = str(uuid.uuid4())
        info = device_info()

        return {
            "route_id": route_id,
            "cost": best_result["cost_breakdown"]["total"],
            "runtime": round(runtime, 4),
            "route_data": {
                "algorithm": algorithm,
                "device": info["device"],
                "mamba_backend": info["mamba_backend"],
                "vehicles": vehicle_ids,
                "tasks": task_ids or config.task_ids,
                "routes": [{
                    "vehicle_id": vehicle_ids[0] if vehicle_ids else "demo",
                    "route": best_result["route"],
                    "feasible": best_result["feasible"],
                    "violation": best_result.get("violation", ""),
                    "total_distance_km": best_result["total_distance_km"],
                    "total_time_min": best_result["total_time_min"],
                    "cost_breakdown": best_result["cost_breakdown"],
                    "charge_plan": best_result.get("charge_plan"),
                    "legs": best_result.get("legs"),
                    "soc_trajectory": best_result.get("soc_trajectory"),
                    "node_positions": best_result.get("node_positions"),
                }],
                "cost_breakdown": best_result["cost_breakdown"],
                "feasible": best_result["feasible"],
                "route": best_result["route"],
                "charge_plan": best_result.get("charge_plan"),
                "soc_trajectory": best_result.get("soc_trajectory"),
                "node_positions": best_result.get("node_positions"),
            },
        }
