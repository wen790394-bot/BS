FROM state-spaces/mamba/mamba-ssm_causal-convld:v2

WORKDIR /app

# 安装 FastAPI 等 Web 依赖（镜像内已有 torch / mamba_ssm / causal_conv1d）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV RL_BACKEND=auto
ENV USE_GPU=true
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "run.py"]
