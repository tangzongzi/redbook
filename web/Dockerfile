# ============================================
# 小红书自动发布系统 - Web 服务
# 多阶段构建，减小镜像体积
# ============================================

# 阶段 1: 构建依赖
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装编译依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 阶段 2: 运行环境
FROM python:3.11-slim AS runner

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 创建必要目录并设置权限
RUN mkdir -p /app/data /app/config /app/logs /app/src && \
    chown -R appuser:appuser /app

# 复制应用代码
COPY --chown=appuser:appuser web/app.py web/dashboard.html ./
COPY --chown=appuser:appuser src/*.py /app/src/

# 确保 __init__.py 存在
RUN touch /app/src/__init__.py

# 切换到非 root 用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/stats || exit 1

EXPOSE 8080

CMD ["python", "app.py"]
