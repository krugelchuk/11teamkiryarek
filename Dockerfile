FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY app ./app
COPY fixtures ./fixtures
COPY content ./content
COPY server.py API_CONTRACT.md README.md ./
COPY --from=frontend /build/dist ./frontend/dist
RUN mkdir -p /app/data && useradd --system --uid 10001 jana && chown -R jana:jana /app
USER jana
ENV HOST=0.0.0.0 PORT=8000 DATABASE_PATH=/app/data/jana_hr.db PYTHONUNBUFFERED=1 FRONTEND_DIR=/app/frontend/dist
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1
CMD ["python", "server.py"]
