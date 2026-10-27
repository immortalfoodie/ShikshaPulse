# ShikshaPulse: one container serves the API and the built React app on one URL.
# Works on Render (Docker web service), Hugging Face Spaces (Docker), Railway, Fly.io or any VM.

# 1) Build the frontend
FROM node:24-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Python app
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN useradd -m -u 1000 app
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=web /app/frontend/dist /app/frontend/dist
# Build the synthetic demo warehouse now (about 30 s), so a cold start serves in seconds.
# No secrets are needed or baked in: the LLM is off for this step.
RUN rm -rf data && LLM_DISABLED=1 python -c "from app import db, runtime; db.engine(); runtime.bootstrap()" \
    && chown -R app:app /app
USER app
ENV PORT=8000 PUBLIC_DEMO=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
