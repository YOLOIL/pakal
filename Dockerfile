FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APPS_ROOT=/mnt/apps \
    DATA_DIR=/data \
    PORT=8971

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY main.py .
COPY pakal ./pakal
COPY static ./static

RUN useradd --system --uid 1000 --no-create-home pakal \
    && mkdir -p /mnt/apps /data \
    && chown -R pakal:pakal /app /data
USER pakal

# SQLite database, cache.json, extracted icons and admin uploads.
VOLUME ["/data"]

EXPOSE 8971

# python:3.11-slim ships without curl, so the probe uses the Python standard library.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8971/api/health', timeout=5).status == 200 else 1)"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8971", "--proxy-headers", "--forwarded-allow-ips=*"]
