FROM python:3.12-slim

# git: python-miio is pinned to a commit on master
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY core/ ./core/
RUN pip install --no-cache-dir ./core

RUN mkdir -p /data && chown nobody /data
ENV OC_DB_PATH=/data/opencook.db
VOLUME /data

USER nobody
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/healthz')"
CMD ["uvicorn", "--factory", "opencook.api.app:create_app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
