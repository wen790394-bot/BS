from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import settings
from app.database import Base, engine


def _print_startup_banner() -> None:
    from app.services.rl.device import device_info

    info = device_info()
    print()
    print("=" * 60)
    print("  电动物流车智能调度系统 — 后端已启动")
    print("=" * 60)
    print(f"  设备: {info['device']}  |  Mamba: {info['mamba_backend']}")
    print(f"  健康检查: curl http://localhost:8000/health")
    print(f"  终端演示: cd backend && python scripts/run_demo.py")
    print("=" * 60)
    print()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _print_startup_banner()
    yield


app = FastAPI(
    title="电动物流车智能调度系统",
    description="路径规划与充电调度一体化决策 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


from app.services.rl.device import device_info


@app.get("/health")
def health_check():
    info = device_info()
    return {
        "status": "ok",
        "device": info["device"],
        "cuda_available": info["cuda_available"],
        "mamba_backend": info["mamba_backend"],
    }
