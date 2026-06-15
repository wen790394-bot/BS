from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schedule import ScheduleRequest, ScheduleResponse, TrainRequest
from app.services.rl.device import device_info
from app.services.rl.ppo_trainer import PPOTrainer
from app.utils.terminal_output import log_decision_summary

router = APIRouter()
ppo_trainer = PPOTrainer()


def _finish_decision(result: dict) -> ScheduleResponse:
    log_decision_summary(result)
    return ScheduleResponse(**result)


@router.post("/run", response_model=ScheduleResponse)
def run_decision(payload: ScheduleRequest, db: Session = Depends(get_db)):
    """智能决策：Mamba-PPO 联合路径与充电策略"""
    try:
        if payload.train_episodes:
            ppo_trainer.train(episodes=payload.train_episodes, algorithm=payload.algorithm)

        result = ppo_trainer.infer(
            vehicle_ids=payload.vehicle_ids,
            task_ids=payload.task_ids,
            algorithm=payload.algorithm,
            use_demo=payload.use_demo or not payload.vehicle_ids,
            db=db if not payload.use_demo and payload.vehicle_ids else None,
            battery_capacity_kwh=payload.battery_capacity_kwh,
            initial_soc=payload.initial_soc,
            soh=payload.soh,
            speed_kmh=payload.speed_kmh,
            temperature=payload.temperature,
        )
        return _finish_decision(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/train")
def train_decision(payload: TrainRequest):
    """PPO 策略训练"""
    return ppo_trainer.train(episodes=payload.episodes, algorithm=payload.algorithm)


@router.get("/demo", response_model=ScheduleResponse)
def demo_decision():
    """演示：Mamba-PPO 智能决策"""
    result = ppo_trainer.infer(algorithm="mamba_ppo", use_demo=True)
    return _finish_decision(result)


@router.get("/algorithms")
def list_algorithms():
    info = device_info()
    return {
        "device": info["device"],
        "mamba_backend": info["mamba_backend"],
        "algorithms": [
            {"id": "mamba_ppo", "name": "Mamba-PPO", "description": "Mamba 时序编码 + PPO 策略优化"},
            {"id": "transformer_ppo", "name": "Transformer-PPO", "description": "Transformer 注意力编码 + PPO"},
            {"id": "ppo", "name": "PPO", "description": "基础 PPO（无序列编码器）"},
            {"id": "ga", "name": "GA", "description": "遗传算法（对比基线，调用路径优化）"},
            {"id": "alns", "name": "ALNS", "description": "自适应大邻域搜索（对比基线）"},
        ]
    }
