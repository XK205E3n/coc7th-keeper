# ---- 多阶段构建：前端（Node）→ 运行（Python）----
# 使用：docker build -t coc-web .
# 运行：docker run --rm -p 18000:18000 -v coc-web-data:/app/data coc-web

# ---- 阶段 1：构建前端静态产物 ----
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---- 阶段 2：运行（uvicorn 单容器：后端 + 前端静态产物）----
FROM python:3.12-slim
WORKDIR /app

COPY server/ server/
COPY modules/ modules/
COPY prompts/ prompts/
COPY --from=frontend /app/frontend/dist frontend/dist

RUN pip install --no-cache-dir fastapi "uvicorn[standard]" openai httpx

# 运行时数据（config.json / secrets.json / games/*.db）挂载卷
ENV DATA_DIR=/app/data
VOLUME ["/app/data"]

EXPOSE 18000
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "18000", "--log-level", "warning"]
