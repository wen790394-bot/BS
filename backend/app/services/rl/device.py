"""PyTorch 设备与 Mamba 后端检测。"""

from __future__ import annotations

import torch

from app.config import settings

_MAMBA_BACKEND: str | None = None


def get_torch_device() -> torch.device:
    if settings.device:
        return torch.device(settings.device)
    if settings.use_gpu and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def get_mamba_backend() -> str:
    """返回 mamba_ssm / pytorch_ssm / numpy。"""
    global _MAMBA_BACKEND
    if _MAMBA_BACKEND is not None:
        return _MAMBA_BACKEND

    if settings.rl_backend == "numpy":
        _MAMBA_BACKEND = "numpy"
        return _MAMBA_BACKEND

    try:
        from mamba_ssm import Mamba  # noqa: F401

        _MAMBA_BACKEND = "mamba_ssm"
    except ImportError:
        _MAMBA_BACKEND = "pytorch_ssm"
    return _MAMBA_BACKEND


def device_info() -> dict:
    device = get_torch_device()
    return {
        "device": str(device),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "mamba_backend": get_mamba_backend(),
        "rl_backend": settings.rl_backend,
    }
