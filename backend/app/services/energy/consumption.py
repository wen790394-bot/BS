"""车辆动力学能耗模型: F = F_r + F_g + F_a, P = Fv/η"""

import math

from app.services.energy.vehicle_params import DEFAULT_VEHICLE_PARAMS, VehicleDynamicsParams


class EnergyConsumptionService:
    def __init__(self, params: VehicleDynamicsParams | None = None):
        self.params = params or DEFAULT_VEHICLE_PARAMS

    def compute_force(self, speed_kmh: float, grade: float = 0.0) -> float:
        """计算行驶阻力 (N)。"""
        p = self.params
        v_ms = max(speed_kmh, 0.1) / 3.6
        f_r = p.rolling_resistance * p.mass_kg * p.gravity * math.cos(grade)
        f_g = p.mass_kg * p.gravity * math.sin(grade)
        f_a = 0.5 * p.air_density * p.drag_coefficient * p.frontal_area_m2 * v_ms**2
        return f_r + f_g + f_a

    def compute_power_kw(self, speed_kmh: float, grade: float = 0.0) -> float:
        """瞬时驱动功率 (kW)。"""
        p = self.params
        v_ms = max(speed_kmh, 0.1) / 3.6
        force = self.compute_force(speed_kmh, grade)
        return force * v_ms / 1000.0 / p.drivetrain_efficiency

    def compute_energy(self, distance_km: float, speed_kmh: float, grade: float = 0.0) -> float:
        """路段能耗 (kWh)。"""
        if distance_km <= 0:
            return 0.0
        power_kw = self.compute_power_kw(speed_kmh, grade)
        travel_hours = distance_km / max(speed_kmh, 0.1)
        return power_kw * travel_hours

    def soc_consumption(self, energy_kwh: float, battery_capacity_kwh: float) -> float:
        """能耗对应的 SOC 下降量。"""
        if battery_capacity_kwh <= 0:
            return 0.0
        return energy_kwh / battery_capacity_kwh
