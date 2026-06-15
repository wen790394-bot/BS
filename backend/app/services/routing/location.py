"""路网节点与距离计算。"""

import math
import re
from dataclasses import dataclass


@dataclass
class RouteNode:
    node_id: str
    x: float
    y: float
    node_type: str = "task"  # depot | task | charge
    demand: float = 0.0
    service_time: float = 0.0
    tw_start: float = 0.0
    tw_end: float = 1440.0
    charge_power_kw: float = 60.0
    charge_price: float = 1.2
    queue: int = 0


def parse_location(location: str, default: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    """解析坐标字符串，支持 'x,y' 格式（单位 km）。"""
    if not location:
        return default
    match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", location.strip())
    if match:
        return float(match.group(1)), float(match.group(2))
    return default


def euclidean_distance(a: RouteNode, b: RouteNode) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def travel_time_minutes(distance_km: float, speed_kmh: float) -> float:
    if speed_kmh <= 0:
        return 0.0
    return distance_km / speed_kmh * 60.0
