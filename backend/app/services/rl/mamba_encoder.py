"""Mamba / Transformer 时序编码器：优先 mamba_ssm (GPU)，回退 PyTorch SSM / NumPy。"""

from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn

from app.services.rl.device import get_mamba_backend, get_torch_device


class SelectiveSSMBlock(nn.Module):
    """纯 PyTorch 选择性 SSM，在无 mamba_ssm 时使用。"""

    def __init__(self, d_model: int, d_state: int = 16):
        super().__init__()
        self.in_proj = nn.Linear(d_model, d_model)
        self.gate_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.decay = nn.Parameter(torch.ones(d_model) * 0.9)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, D)
        b, length, d = x.shape
        h = torch.zeros(b, d, device=x.device, dtype=x.dtype)
        outputs = []
        decay = torch.sigmoid(self.decay)
        for t in range(length):
            xt = x[:, t, :]
            gate = torch.sigmoid(self.gate_proj(xt))
            inp = torch.tanh(self.in_proj(xt))
            h = decay.unsqueeze(0) * h + gate * inp
            outputs.append(h.unsqueeze(1))
        return self.out_proj(torch.cat(outputs, dim=1))


class TorchMambaEncoder(nn.Module):
    """Mamba 时序编码：mamba_ssm 可用时用官方 Mamba 块，否则用 PyTorch SSM。"""

    def __init__(self, input_dim: int = 12, d_model: int = 64, d_state: int = 16):
        super().__init__()
        self.input_dim = input_dim
        self.d_model = d_model
        self.input_proj = nn.Linear(input_dim, d_model)
        self.backend = get_mamba_backend()

        if self.backend == "mamba_ssm":
            from mamba_ssm import Mamba

            self.core = Mamba(d_model=d_model, d_state=d_state, d_conv=4, expand=2)
        else:
            self.core = SelectiveSSMBlock(d_model, d_state)

        self.norm = nn.LayerNorm(d_model)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:
        # seq: (B, L, input_dim)
        if seq.ndim == 2:
            seq = seq.unsqueeze(0)
        x = self.input_proj(seq)
        x = self.core(x)
        x = self.norm(x)
        return x[:, -1, :]


class TorchTransformerEncoder(nn.Module):
    """简化 Transformer 编码器（PyTorch）。"""

    def __init__(self, input_dim: int = 12, d_model: int = 64, nhead: int = 4):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 2,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=1)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, seq: torch.Tensor) -> torch.Tensor:
        if seq.ndim == 2:
            seq = seq.unsqueeze(0)
        x = self.input_proj(seq)
        x = self.encoder(x)
        x = self.norm(x)
        return x.mean(dim=1)


def sequence_to_tensor(
    state_sequence: list[list[float]] | np.ndarray,
    device: torch.device | None = None,
) -> torch.Tensor:
    device = device or get_torch_device()
    if len(state_sequence) == 0:
        return torch.zeros(1, 1, 12, device=device)
    arr = np.asarray(state_sequence, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return torch.from_numpy(arr).unsqueeze(0).to(device)


# ---- NumPy 轻量实现（rl_backend=numpy 时使用）----


class MambaEncoder:
    """轻量级选择性 SSM（纯 NumPy）。"""

    def __init__(self, input_dim: int = 12, hidden_dim: int = 64, output_dim: int = 64, seed: int = 42):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        rng = np.random.default_rng(seed)
        scale = 1.0 / math.sqrt(input_dim)
        self.W_gate = rng.normal(0, scale, (input_dim, hidden_dim))
        self.W_B = rng.normal(0, scale, (input_dim, hidden_dim))
        self.W_C = rng.normal(0, scale, (hidden_dim, output_dim))
        self.D = rng.normal(0, 0.1, output_dim)
        self.decay = np.exp(-np.abs(rng.normal(0.3, 0.1, hidden_dim)))

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -20, 20)))

    def encode(self, state_sequence: list[list[float]] | np.ndarray) -> np.ndarray:
        if len(state_sequence) == 0:
            return np.zeros(self.output_dim)

        seq = np.asarray(state_sequence, dtype=np.float64)
        if seq.ndim == 1:
            seq = seq.reshape(1, -1)

        h = np.zeros(self.hidden_dim)
        for x in seq:
            x = np.asarray(x, dtype=np.float64)
            gate = self._sigmoid(x @ self.W_gate)
            b = np.tanh(x @ self.W_B)
            h = self.decay * h + gate * b

        y = h @ self.W_C + self.D * np.mean(seq, axis=0)[: self.output_dim].sum() / max(len(seq), 1)
        return np.tanh(y)


class TransformerEncoder:
    """简化 Transformer 编码器（NumPy）。"""

    def __init__(self, input_dim: int = 12, hidden_dim: int = 64, output_dim: int = 64, seed: int = 7):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        rng = np.random.default_rng(seed)
        scale = 1.0 / math.sqrt(input_dim)
        self.W_q = rng.normal(0, scale, (input_dim, hidden_dim))
        self.W_k = rng.normal(0, scale, (input_dim, hidden_dim))
        self.W_v = rng.normal(0, scale, (input_dim, hidden_dim))
        self.W_o = rng.normal(0, scale, (hidden_dim, output_dim))

    def encode(self, state_sequence: list[list[float]] | np.ndarray) -> np.ndarray:
        if len(state_sequence) == 0:
            return np.zeros(self.output_dim)

        seq = np.asarray(state_sequence, dtype=np.float64)
        if seq.ndim == 1:
            seq = seq.reshape(1, -1)

        q = seq @ self.W_q
        k = seq @ self.W_k
        v = seq @ self.W_v
        scores = q @ k.T / math.sqrt(self.hidden_dim)
        scores = scores - np.max(scores, axis=-1, keepdims=True)
        attn = np.exp(scores)
        attn = attn / (np.sum(attn, axis=-1, keepdims=True) + 1e-8)
        context = attn @ v
        pooled = np.mean(context, axis=0)
        return np.tanh(pooled @ self.W_o)
