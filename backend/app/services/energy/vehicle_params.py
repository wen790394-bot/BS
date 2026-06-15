"""电动物流车动力学参数。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleDynamicsParams:
    mass_kg: float = 4500.0
    rolling_resistance: float = 0.012
    drag_coefficient: float = 0.35
    frontal_area_m2: float = 4.5
    drivetrain_efficiency: float = 0.88
    gravity: float = 9.81
    air_density: float = 1.225
    cost_per_km: float = 2.0
    electricity_price: float = 0.8
    soc_min: float = 0.10
    charge_target_soc: float = 0.85


DEFAULT_VEHICLE_PARAMS = VehicleDynamicsParams()
