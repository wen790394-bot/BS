"""一阶 RC 等效电路模型 + 扩展卡尔曼滤波 (EKF) 在线 SOC 估计。"""

from dataclasses import dataclass, field

import numpy as np

from app.services.battery.battery_params import BatteryParams, DEFAULT_PARAMS
from app.services.battery.ocv_curve import ocv_derivative, ocv_voltage


@dataclass
class EKFState:
    soc: float = 0.8
    v1: float = 0.0
    p: np.ndarray = field(default_factory=lambda: np.diag([1e-4, 1e-2]))


class SOCModel:
    """
    状态方程:
        SOC_{k+1} = SOC_k - I_k * dt / (3600 * Q)
        V1_{k+1}  = exp(-dt/τ) * V1_k + R1 * (1 - exp(-dt/τ)) * I_k

    观测方程:
        V_k = OCV(SOC_k) - I_k * R0 - V1_k
    """

    def __init__(self, params: BatteryParams | None = None):
        self.params = params or DEFAULT_PARAMS
        self._state = EKFState()

    @property
    def state(self) -> EKFState:
        return self._state

    def reset(self, soc: float = 0.8, v1: float = 0.0) -> None:
        self._state = EKFState(soc=soc, v1=v1)

    def _effective_r0(self, temperature: float) -> float:
        temp_factor = 1.0 + 0.005 * (25.0 - temperature)
        return self.params.r0 * temp_factor

    def _predict(self, current: float, dt: float) -> None:
        p = self.params
        exp_factor = np.exp(-dt / p.tau)

        soc = self._state.soc - current * dt / (3600.0 * p.capacity_ah)
        soc = float(np.clip(soc, 0.0, 1.0))
        v1 = exp_factor * self._state.v1 + p.r1 * (1.0 - exp_factor) * current

        f_jacobian = np.array([[1.0, 0.0], [0.0, exp_factor]])
        q = np.diag([1e-6, 1e-4])
        p_mat = f_jacobian @ self._state.p @ f_jacobian.T + q

        self._state.soc = soc
        self._state.v1 = v1
        self._state.p = p_mat

    def _update(self, current: float, voltage: float, r0: float) -> None:
        p = self.params
        soc = self._state.soc
        v1 = self._state.v1

        v_pred = ocv_voltage(soc, p.nominal_voltage) - current * r0 - v1
        innovation = voltage - v_pred

        docv = ocv_derivative(soc, p.nominal_voltage)
        h_jacobian = np.array([[docv, -1.0]])
        r = np.array([[0.01**2]])

        s = h_jacobian @ self._state.p @ h_jacobian.T + r
        k = self._state.p @ h_jacobian.T @ np.linalg.inv(s)

        x = np.array([soc, v1]) + (k @ np.array([[innovation]])).flatten()
        x[0] = float(np.clip(x[0], 0.0, 1.0))
        p_mat = (np.eye(2) - k @ h_jacobian) @ self._state.p

        self._state.soc = float(x[0])
        self._state.v1 = float(x[1])
        self._state.p = p_mat

    def estimate_step(
        self,
        current: float,
        voltage: float,
        temperature: float = 25.0,
        dt: float = 1.0,
    ) -> dict:
        """单步 EKF 估计。"""
        r0 = self._effective_r0(temperature)
        self._predict(current, dt)
        self._update(current, voltage, r0)

        v_pred = ocv_voltage(self._state.soc, self.params.nominal_voltage) - current * r0 - self._state.v1
        return {
            "soc": round(self._state.soc, 4),
            "v1": round(self._state.v1, 4),
            "voltage_predicted": round(v_pred, 2),
            "voltage_measured": round(voltage, 2),
            "soc_uncertainty": round(float(np.sqrt(self._state.p[0, 0])), 6),
        }

    def estimate(
        self,
        current: float,
        voltage: float,
        temperature: float = 25.0,
        dt: float = 1.0,
        soc_init: float | None = None,
    ) -> dict:
        if soc_init is not None:
            self.reset(soc=soc_init)
        return self.estimate_step(current, voltage, temperature, dt)

    def simulate(
        self,
        measurements: list[dict],
        soc_init: float = 0.8,
    ) -> list[dict]:
        self.reset(soc=soc_init)
        return [
            self.estimate_step(
                current=m["current"],
                voltage=m["voltage"],
                temperature=m.get("temperature", 25.0),
                dt=m.get("dt", 1.0),
            )
            for m in measurements
        ]

    def coulomb_count(self, current: float, dt: float, soc_init: float) -> float:
        delta = current * dt / (3600.0 * self.params.capacity_ah)
        return float(np.clip(soc_init - delta, 0.0, 1.0))
