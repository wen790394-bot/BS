"""充电调度成本参数。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChargeSchedulingParams:
    """充电调度目标 min(C_charge + C_waiting) 的系数。"""

    default_charge_price: float = 1.2  # 默认充电站电价 元/kWh
    waiting_cost_per_min: float = 0.5  # 时间窗等待惩罚 元/min
    queue_wait_per_vehicle_min: float = 5.0  # 排队每车额外等待 元/min 折算
    min_charge_soc_step: float = 0.05  # 充电量优化步长 (SOC 比例)


DEFAULT_CHARGE_PARAMS = ChargeSchedulingParams()
