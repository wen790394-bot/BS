"""OCV-SOC 曲线及导数，用于 ECM 与 EKF 观测方程。"""

import numpy as np

# 商用磷酸铁锂包 OCV 曲线 (SOC, 归一化端电压 V/V_nom)
_SOC_TABLE = np.array([0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0])
_V_RATIO_TABLE = np.array([0.750, 0.780, 0.800, 0.825, 0.850, 0.875, 0.900, 0.925, 0.950, 0.975, 1.000, 1.010, 1.025])


def ocv_voltage(soc: float, v_nom: float = 400.0) -> float:
    """根据 SOC 查表插值得到开路电压 (V)。"""
    soc_clamped = float(np.clip(soc, 0.0, 1.0))
    ratio = float(np.interp(soc_clamped, _SOC_TABLE, _V_RATIO_TABLE))
    return ratio * v_nom


def ocv_derivative(soc: float, v_nom: float = 400.0) -> float:
    """d(OCV)/d(SOC)，用于 EKF 雅可比。"""
    soc_clamped = float(np.clip(soc, 0.001, 0.999))
    ds = 1e-4
    v_plus = ocv_voltage(soc_clamped + ds, v_nom)
    v_minus = ocv_voltage(soc_clamped - ds, v_nom)
    return (v_plus - v_minus) / (2 * ds)
