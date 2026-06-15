from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./ev_scheduler.db"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    # RL / GPU：auto=优先 CUDA+mamba_ssm；numpy=纯 NumPy 轻量模式
    rl_backend: str = "auto"
    use_gpu: bool = True
    device: str = ""
    bootstrap_episodes: int = 80
    ppo_lr: float = 3e-4
    ppo_clip_eps: float = 0.2
    ppo_gamma: float = 0.99
    ppo_gae_lambda: float = 0.95

    class Config:
        env_file = ".env"


settings = Settings()
