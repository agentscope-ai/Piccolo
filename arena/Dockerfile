FROM node:22-bookworm-slim AS engine-runtime

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/jev-browsers \
    JEV_DATA_DIR=/data \
    JEV_LEADERBOARD_DIR=/app/leaderboard \
    JEV_PREFIX=""

COPY --from=engine-runtime /usr/local/bin/node /usr/local/bin/node

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium \
    && groupadd --gid 10001 jev \
    && useradd --uid 10001 --gid jev --create-home jev \
    && mkdir -p /data \
    && chown jev:jev /data \
    && chmod -R a+rX /opt/jev-browsers \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=jev:jev . ./
USER jev
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:8080'+os.environ.get('JEV_PREFIX','').rstrip('/')+'/api/health',timeout=4).close()"
CMD ["python", "-m", "blink_arena", "--host", "0.0.0.0", "--port", "8080"]
