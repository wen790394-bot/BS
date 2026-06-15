"""终端友好输出格式。"""

from __future__ import annotations

from typing import Any


def _line(char: str = "─", width: int = 60) -> str:
    return char * width


def print_header(title: str) -> None:
    print()
    print(_line("═"))
    print(f"  {title}")
    print(_line("═"))


def print_section(title: str) -> None:
    print()
    print(f"▶ {title}")
    print(_line())


def print_system_info(info: dict[str, Any]) -> None:
    print_header("系统状态")
    print(f"  计算设备     : {info.get('device', '-')}")
    print(f"  CUDA 可用    : {'是' if info.get('cuda_available') else '否'}")
    if info.get("cuda_device_name"):
        print(f"  GPU 型号     : {info['cuda_device_name']}")
    print(f"  Mamba 后端   : {info.get('mamba_backend', '-')}")
    print(f"  RL 模式      : {info.get('rl_backend', '-')}")


def print_import_result(source: str, created: dict[str, int], data: dict[str, list]) -> None:
    print_header("数据导入")
    print(f"  数据来源     : {source}")
    print(f"  新增车辆     : {created.get('vehicles', 0)}")
    print(f"  新增订单     : {created.get('tasks', 0)}")
    print(f"  新增充电站   : {created.get('stations', 0)}")
    print(f"  车辆列表     : {[v['vehicle_id'] for v in data.get('vehicles', [])]}")
    print(f"  订单列表     : {[t['task_id'] for t in data.get('tasks', [])]}")
    print(f"  充电站列表   : {[s['station_id'] for s in data.get('charge_stations', [])]}")


def log_decision_summary(result: dict[str, Any]) -> None:
    """服务端终端一行摘要（API 调用时打印）。"""
    route_data = result.get("route_data") or {}
    routes = route_data.get("routes") or []
    route_str = ""
    if routes:
        nodes = routes[0].get("route") or []
        route_str = " → ".join(nodes)
    print(
        f"[决策] 算法={route_data.get('algorithm', '?')} | "
        f"成本={result.get('cost', 0):.2f} | "
        f"耗时={result.get('runtime', 0):.3f}s | "
        f"路径: {route_str}"
    )


def print_schedule_result(result: dict[str, Any]) -> None:
    print_header("智能决策结果")
    print(f"  方案 ID      : {result.get('route_id', '-')}")
    print(f"  总成本       : {result.get('cost', 0):.2f} 元")
    print(f"  计算耗时     : {result.get('runtime', 0):.3f} 秒")

    route_data = result.get("route_data") or {}
    if not route_data:
        return

    print_section("算法与输入")
    print(f"  算法         : {route_data.get('algorithm', '-')}")
    print(f"  设备         : {route_data.get('device', '-')}")
    tasks = route_data.get("tasks") or []
    vehicles = route_data.get("vehicles") or []
    if tasks:
        print(f"  订单         : {tasks}")
    if vehicles:
        print(f"  车辆         : {vehicles}")

    routes = route_data.get("routes") or []
    for idx, route in enumerate(routes, 1):
        print_section(f"路线 {idx} — 车辆 {route.get('vehicle_id', '?')}")
        route_nodes = route.get("route") or []
        print(f"  路径         : {' → '.join(route_nodes)}")
        print(f"  可行         : {'是' if route.get('feasible') else '否'}")
        if route.get("violation"):
            print(f"  约束违反     : {route['violation']}")
        print(f"  总里程       : {route.get('total_distance_km', 0):.2f} km")
        print(f"  总时间       : {route.get('total_time_min', 0):.2f} min")

        breakdown = route.get("cost_breakdown") or {}
        if breakdown:
            print()
            print("  成本明细:")
            print(f"    行驶成本   : {breakdown.get('travel', 0):.2f}")
            print(f"    能耗成本   : {breakdown.get('energy', 0):.2f}")
            print(f"    充电成本   : {breakdown.get('charge', 0):.2f}")
            print(f"    等待成本   : {breakdown.get('waiting', 0):.2f}")
            print(f"    退化成本   : {breakdown.get('degradation', 0):.4f}")
            print(f"    合计       : {breakdown.get('total', 0):.2f}")

        charge_plan = route.get("charge_plan") or {}
        plans = charge_plan.get("plans") or []
        if plans:
            print()
            print("  充电计划:")
            for plan in plans:
                print(
                    f"    站点 {plan.get('station_id')} | "
                    f"充电 {plan.get('charge_kwh', 0):.2f} kWh | "
                    f"SOC {plan.get('soc_before', 0):.2%} → {plan.get('soc_after', 0):.2%} | "
                    f"费用 {plan.get('charge_cost', 0):.2f} 元"
                )

        legs = route.get("legs") or []
        if legs:
            print()
            print("  路段明细:")
            for leg in legs:
                print(
                    f"    {leg.get('from')} → {leg.get('to')} | "
                    f"{leg.get('distance_km', 0):.2f} km | "
                    f"耗时 {leg.get('travel_time_min', 0):.1f} min | "
                    f"SOC {leg.get('soc_before', 0):.2%} → {leg.get('soc_after', 0):.2%}"
                )

    print()
    print(_line("═"))
    print("  决策完成")
    print(_line("═"))
    print()
