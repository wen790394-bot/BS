"""电池退化成本: C_deg = ΔSOH × C_battery"""

from app.services.battery.battery_params import BatteryParams, DEFAULT_PARAMS
from app.services.battery.soh_model import SOHModel


class DegradationCostService:
    def __init__(self, params: BatteryParams | None = None):
        self.params = params or DEFAULT_PARAMS
        self.soh_model = SOHModel(self.params)

    def compute(self, delta_soh: float, battery_cost: float | None = None) -> dict:
        cost_battery = battery_cost if battery_cost is not None else self.params.battery_cost
        c_deg = delta_soh * cost_battery
        return {
            "degradation_cost": round(c_deg, 2),
            "delta_soh": round(delta_soh, 8),
            "battery_cost": cost_battery,
        }

    def compute_from_operation(
        self,
        soc: float,
        soh: float,
        dod: float,
        temperature: float,
        duration_hours: float = 0.0,
        battery_cost: float | None = None,
    ) -> dict:
        """根据一次运营工况计算退化成本及明细。"""
        health = self.soh_model.estimate(
            soc=soc,
            soh=soh,
            dod=dod,
            temperature=temperature,
            duration_hours=duration_hours,
        )
        cost = self.compute(health["delta_soh"], battery_cost)
        return {**health, **cost}
