"""Actor-Critic：PyTorch + Mamba/Transformer（GPU），或 NumPy 轻量模式。"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.config import settings
from app.services.rl.device import get_torch_device
from app.services.rl.env import SchedulingEnv
from app.services.rl.mamba_encoder import (
    MambaEncoder,
    TorchMambaEncoder,
    TorchTransformerEncoder,
    TransformerEncoder,
    sequence_to_tensor,
)


def _softmax_np(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    exp_x = np.exp(np.clip(x, -20, 20))
    return exp_x / (np.sum(exp_x) + 1e-8)


class TorchActorCritic(nn.Module):
    ACTION_FEAT_DIM = 8

    def __init__(self, algorithm: str = "mamba_ppo", state_dim: int = 12, encode_dim: int = 64):
        super().__init__()
        self.algorithm = algorithm
        self.state_dim = state_dim
        self.encode_dim = encode_dim

        if algorithm == "transformer_ppo":
            self.encoder: nn.Module | None = TorchTransformerEncoder(state_dim, encode_dim)
        elif algorithm == "mamba_ppo":
            self.encoder = TorchMambaEncoder(state_dim, encode_dim)
        else:
            self.encoder = None

        actor_in = (encode_dim if self.encoder else state_dim) + self.ACTION_FEAT_DIM
        self.actor = nn.Sequential(
            nn.Linear(actor_in, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )
        critic_in = encode_dim if self.encoder else state_dim
        self.critic = nn.Sequential(
            nn.Linear(critic_in, 64),
            nn.Tanh(),
            nn.Linear(64, 1),
        )

    def encode_state(self, state: dict) -> torch.Tensor:
        if self.encoder is None:
            vec = torch.tensor(state["vector"], dtype=torch.float32, device=self._device())
            return vec.unsqueeze(0)
        seq = sequence_to_tensor(state.get("state_sequence", [state["vector"]]), self._device())
        return self.encoder(seq)

    def _device(self) -> torch.device:
        return next(self.parameters()).device

    @staticmethod
    def action_features(state: dict, candidate_id: str) -> torch.Tensor:
        nodes = state["nodes"]
        cur = nodes[state["position"]["node_id"]]
        cand = nodes[candidate_id]
        dist = math.hypot(cur.x - cand.x, cur.y - cand.y) / 20.0
        is_task = 1.0 if cand.node_type == "task" else 0.0
        is_charge = 1.0 if cand.node_type == "charge" else 0.0
        is_depot = 1.0 if cand.node_type == "depot" else 0.0
        tw_slack = max(0.0, cand.tw_end - state["time_min"]) / 1440.0
        price = cand.charge_price / 2.0 if cand.node_type == "charge" else 0.0
        queue = cand.queue / 5.0 if cand.node_type == "charge" else 0.0
        urgency = 1.0 if candidate_id in state.get("unvisited_tasks", []) else 0.0
        return torch.tensor(
            [dist, is_task, is_charge, is_depot, tw_slack, price, queue, urgency],
            dtype=torch.float32,
        )

    def score_candidates(
        self,
        state: dict,
        candidates: list[str],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        embedding = self.encode_state(state).squeeze(0)
        logits = []
        for cid in candidates:
            feat = self.action_features(state, cid).to(embedding.device)
            x = torch.cat([embedding, feat])
            logits.append(self.actor(x).squeeze())
        return torch.stack(logits), embedding

    def evaluate(self, state: dict) -> torch.Tensor:
        embedding = self.encode_state(state).squeeze(0)
        return self.critic(embedding).squeeze()

    def act(
        self,
        state: dict,
        deterministic: bool = False,
        temperature: float = 1.0,
    ) -> dict[str, Any]:
        candidates = state.get("feasible_actions") or []
        if not candidates:
            return {"next_node": None, "charge": False, "charge_amount": 0.0, "log_prob": 0.0}

        with torch.no_grad():
            logits, _ = self.score_candidates(state, candidates)
            if deterministic:
                idx = int(torch.argmax(logits).item())
            else:
                probs = F.softmax(logits / max(temperature, 0.1), dim=0)
                idx = int(torch.multinomial(probs, 1).item())

            probs = F.softmax(logits / max(temperature, 0.1), dim=0)
            log_prob = float(torch.log(probs[idx] + 1e-8).item())

        chosen = candidates[idx]
        node = state["nodes"][chosen]
        charge = False
        charge_amount = 0.0
        charge_target_soc = None
        if node.node_type == "charge" and state["soc"] < 0.85:
            charge = True
            charge_target_soc = min(0.85, state["soc"] + 0.3)
            charge_amount = max(0.0, (charge_target_soc - state["soc"]) * state.get("battery_capacity_kwh", 60.0))

        return {
            "next_node": chosen,
            "charge": charge,
            "charge_amount": round(charge_amount, 4),
            "charge_target_soc": charge_target_soc,
            "log_prob": log_prob,
            "action_idx": idx,
            "candidates": candidates,
            "probs": probs.cpu().tolist(),
        }

    def select_action_with_value(self, state: dict, deterministic: bool = False) -> tuple[dict, float]:
        action = self.act(state, deterministic=deterministic)
        with torch.no_grad():
            value = float(self.evaluate(state).item())
        action["value"] = value
        return action, value


class NumpyActorCritic:
    """NumPy 版 Actor-Critic（rl_backend=numpy）。"""

    ACTION_FEAT_DIM = 8

    def __init__(self, algorithm: str = "mamba_ppo", seed: int = 42):
        self.algorithm = algorithm
        self.rng = np.random.default_rng(seed)
        self.state_dim = SchedulingEnv.STATE_DIM

        if algorithm == "transformer_ppo":
            self.encoder = TransformerEncoder(self.state_dim, 64, 64, seed=seed)
            self.encode_dim = 64
        elif algorithm == "mamba_ppo":
            self.encoder = MambaEncoder(self.state_dim, 64, 64, seed=seed)
            self.encode_dim = 64
        else:
            self.encoder = None
            self.encode_dim = self.state_dim

        hidden = 64
        in_dim = self.encode_dim + self.ACTION_FEAT_DIM
        scale = 1.0 / math.sqrt(in_dim)
        self.W_actor = self.rng.normal(0, scale, (in_dim, hidden))
        self.b_actor = np.zeros(hidden)
        self.W_actor_out = self.rng.normal(0, scale, (hidden, 1))
        self.W_critic = self.rng.normal(0, scale, (self.encode_dim, hidden))
        self.b_critic = np.zeros(hidden)
        self.W_critic_out = self.rng.normal(0, scale, (hidden, 1))

    def _encode(self, state: dict) -> np.ndarray:
        if self.encoder is None:
            return np.asarray(state["vector"], dtype=np.float64)
        return self.encoder.encode(state.get("state_sequence", [state["vector"]]))

    def _action_features(self, state: dict, candidate_id: str) -> np.ndarray:
        nodes = state["nodes"]
        cur = nodes[state["position"]["node_id"]]
        cand = nodes[candidate_id]
        dist = math.hypot(cur.x - cand.x, cur.y - cand.y) / 20.0
        is_task = 1.0 if cand.node_type == "task" else 0.0
        is_charge = 1.0 if cand.node_type == "charge" else 0.0
        is_depot = 1.0 if cand.node_type == "depot" else 0.0
        tw_slack = max(0.0, cand.tw_end - state["time_min"]) / 1440.0
        price = cand.charge_price / 2.0 if cand.node_type == "charge" else 0.0
        queue = cand.queue / 5.0 if cand.node_type == "charge" else 0.0
        urgency = 1.0 if candidate_id in state.get("unvisited_tasks", []) else 0.0
        return np.array([dist, is_task, is_charge, is_depot, tw_slack, price, queue, urgency])

    def _score_candidates(self, state: dict, candidates: list[str]) -> tuple[np.ndarray, np.ndarray]:
        embedding = self._encode(state)
        logits = []
        for cid in candidates:
            feat = self._action_features(state, cid)
            x = np.concatenate([embedding, feat])
            h = np.tanh(x @ self.W_actor + self.b_actor)
            logits.append(float((h @ self.W_actor_out).squeeze()))
        return np.array(logits), embedding

    def act(self, state: dict, deterministic: bool = False, temperature: float = 1.0) -> dict:
        candidates = state.get("feasible_actions") or []
        if not candidates:
            return {"next_node": None, "charge": False, "charge_amount": 0.0, "log_prob": 0.0}

        logits, _ = self._score_candidates(state, candidates)
        if deterministic:
            idx = int(np.argmax(logits))
        else:
            probs = _softmax_np(logits / max(temperature, 0.1))
            idx = int(self.rng.choice(len(candidates), p=probs))

        probs = _softmax_np(logits / max(temperature, 0.1))
        log_prob = float(np.log(probs[idx] + 1e-8))
        chosen = candidates[idx]
        node = state["nodes"][chosen]

        charge = False
        charge_amount = 0.0
        charge_target_soc = None
        if node.node_type == "charge" and state["soc"] < 0.85:
            charge = True
            charge_target_soc = min(0.85, state["soc"] + 0.3)
            charge_amount = max(0.0, (charge_target_soc - state["soc"]) * state.get("battery_capacity_kwh", 60.0))

        return {
            "next_node": chosen,
            "charge": charge,
            "charge_amount": round(charge_amount, 4),
            "charge_target_soc": charge_target_soc,
            "log_prob": log_prob,
            "action_idx": idx,
            "candidates": candidates,
            "probs": probs.tolist(),
        }

    def evaluate(self, state: dict) -> float:
        embedding = self._encode(state)
        h = np.tanh(embedding @ self.W_critic + self.b_critic)
        return float((h @ self.W_critic_out).squeeze())

    def select_action_with_value(self, state: dict, deterministic: bool = False) -> tuple[dict, float]:
        action = self.act(state, deterministic=deterministic)
        value = self.evaluate(state)
        action["value"] = value
        return action, value


def create_actor_critic(algorithm: str = "mamba_ppo"):
    if settings.rl_backend == "numpy":
        return NumpyActorCritic(algorithm=algorithm)
    device = get_torch_device()
    model = TorchActorCritic(algorithm=algorithm)
    return model.to(device)


# 向后兼容别名
ActorCritic = create_actor_critic
