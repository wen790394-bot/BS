"""电动物流车动力电池默认参数（磷酸铁锂/商用包）"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryParams:
    """电池包参数，用于 ECM 与退化模型。"""

    # 容量与成本
    capacity_kwh: float = 100.0
    nominal_voltage: float = 400.0
    battery_cost: float = 80000.0  # 元
    soh_eol: float = 0.80  # 寿命终止 SOH

    # 等效电路模型 (ECM) 参数 — 包级
    r0: float = 0.015  # 欧姆内阻 Ω
    r1: float = 0.008  # 极化电阻 Ω
    c1: float = 8000.0  # 极化电容 F

    # 退化模型系数 — 半经验 L = f(DOD, SOC, T)
    k_cycle: float = 2.5e-4  # 循环老化系数
    dod_exponent: float = 1.8  # DOD 指数 β
    ea_cycle: float = 28000.0  # 活化能 J/mol
    k_cal: float = 5.0e-6  # 日历老化系数
    ea_cal: float = 32000.0  # 日历老化活化能 J/mol
    soc_optimal: float = 0.50  # 最优存储 SOC
    soc_stress_factor: float = 0.8  # 高/低 SOC 应力系数

    # 物理常数
    gas_constant: float = 8.314  # J/(mol·K)
    t_ref: float = 298.15  # 参考温度 K

    @property
    def capacity_ah(self) -> float:
        return self.capacity_kwh * 1000.0 / self.nominal_voltage

    @property
    def tau(self) -> float:
        return self.r1 * self.c1


DEFAULT_PARAMS = BatteryParams()
