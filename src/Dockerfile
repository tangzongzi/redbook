# ============================================
# 小红书自动发布系统 - 内容生成器
# ============================================

FROM python:3.11-slim

WORKDIR /app

# 安装依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 创建目录
RUN mkdir -p /app/data /app/config /app/logs && \
    chown -R appuser:appuser /app

# 复制依赖文件
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 复制代码
COPY --chown=appuser:appuser src/*.py ./

USER appuser

# 健康检查
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "scheduler.py"]
