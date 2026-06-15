"""SOH 半经验寿命模型: L = f(DOD, SOC, T)"""

import math

from app.services.battery.battery_params import BatteryParams, DEFAULT_PARAMS


class SOHModel:
    """
    循环老化:
        ΔSOH_cycle = k_c · DOD^β · exp(-Ea/R · (1/T - 1/T_ref)) · g(SOC)

    日历老化:
        ΔSOH_cal = k_cal · exp(-Ea_cal/R · (1/T - 1/T_ref)) · t^0.5 · h(SOC)

    其中 g(SOC) 为 SOC 应力因子，h(SOC) 为存储 SOC 应力。
    """

    def __init__(self, params: BatteryParams | None = None):
        self.params = params or DEFAULT_PARAMS

    def _temperature_factor(self, temperature_c: float, ea: float) -> float:
        t_k = temperature_c + 273.15
        return math.exp(-ea / self.params.gas_constant * (1.0 / t_k - 1.0 / self.params.t_ref))

    def _soc_stress(self, soc: float) -> float:
        """高/低 SOC 循环应力放大因子 g(SOC)。"""
        k = self.params.soc_stress_factor
        low_penalty = k * max(0.0, 0.15 - soc)
        high_penalty = k * max(0.0, soc - 0.85)
        return 1.0 + low_penalty + high_penalty

    def _storage_stress(self, soc: float) -> float:
        """存储 SOC 偏离最优值 h(SOC)。"""
        return 1.0 + 2.0 * abs(soc - self.params.soc_optimal)

    def cycle_degradation(
        self,
        dod: float,
        soc: float,
        temperature: float,
    ) -> float:
        """单次循环（或部分循环）造成的 SOH 衰减量。"""
        p = self.params
        dod = max(dod, 0.01)
        temp_factor = self._temperature_factor(temperature, p.ea_cycle)
        soc_factor = self._soc_stress(soc)
        return p.k_cycle * (dod ** p.dod_exponent) * temp_factor * soc_factor

    def calendar_degradation(
        self,
        soc: float,
        temperature: float,
        duration_hours: float,
    ) -> float:
        """日历老化造成的 SOH 衰减量。"""
        if duration_hours <= 0:
            return 0.0
        p = self.params
        temp_factor = self._temperature_factor(temperature, p.ea_cal)
        storage_factor = self._storage_stress(soc)
        return p.k_cal * temp_factor * storage_factor * math.sqrt(duration_hours)

    def estimate(
        self,
        soc: float,
        soh: float,
        dod: float,
        temperature: float,
        duration_hours: float = 0.0,
    ) -> dict:
        """
        综合评估电池健康状态。

        Returns:
            soh_t: 更新后的 SOH
            delta_soh: 本次衰减量
            degradation_rate: 每等效满充满放循环的 SOH 衰减率
            rul_t: 剩余等效满循环次数 (EFC)
            cycle_degradation: 循环老化分量
            calendar_degradation: 日历老化分量
        """
        delta_cycle = self.cycle_degradation(dod, soc, temperature)
        delta_cal = self.calendar_degradation(soc, temperature, duration_hours)
        delta_soh = delta_cycle + delta_cal

        soh_t = max(soh - delta_soh, self.params.soh_eol)

        efc = max(dod, 0.01)
        rate_per_efc = delta_soh / efc

        remaining = max(soh_t - self.params.soh_eol, 0.0)
        rul_t = remaining / rate_per_efc if rate_per_efc > 1e-10 else float("inf")

        return {
            "soh_t": round(soh_t, 6),
            "delta_soh": round(delta_soh, 8),
            "degradation_rate": round(rate_per_efc, 8),
            "rul_t": round(rul_t, 1) if rul_t != float("inf") else 99999.0,
            "cycle_degradation": round(delta_cycle, 8),
            "calendar_degradation": round(delta_cal, 8),
        }

    def predict_trajectory(
        self,
        soh_init: float,
        dod: float,
        soc: float,
        temperature: float,
        cycles: int = 100,
    ) -> list[dict]:
        """预测 SOH 随等效循环次数的退化轨迹。"""
        trajectory = [{"cycle": 0, "soh": round(soh_init, 6)}]
        soh = soh_init
        for i in range(1, cycles + 1):
            result = self.estimate(soh=soh, soc=soc, dod=dod, temperature=temperature)
            soh = result["soh_t"]
            trajectory.append({"cycle": i, "soh": soh})
            if soh <= self.params.soh_eol:
                break
        return trajectory
