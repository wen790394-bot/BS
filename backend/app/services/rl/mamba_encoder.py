"""Mamba 编码器：选择性状态空间模型，提取历史轨迹与能量时序特征。"""

from __future__ import annotations

import math

import numpy as np


class MambaEncoder:
    """
    轻量级选择性 SSM（纯 NumPy 实现，无需 PyTorch/Mamba-SSM）。

    h_t = decay * h_{t-1} + gate(x_t) * B(x_t)
    y_t = C * h_t + D * x_t
    """

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

    def encode_batch(self, sequences: list[list[list[float]]]) -> np.ndarray:
        return np.stack([self.encode(seq) for seq in sequences])


class TransformerEncoder:
    """简化 Transformer 编码器（自注意力 + 均值池化）。"""

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
