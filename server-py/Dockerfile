# Cold Case — backend dev image.
# Uvicorn with --reload picks up source changes via the bind-mount in
# docker-compose.yml. For a production image, multi-stage build with
# `pip install --no-cache-dir` and run without --reload.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps for reportlab (image libraries are not strictly required for
# the basic LETTER-format PDFs we render, but pin them anyway for parity
# with darker production images that may render charts).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Source is bind-mounted at runtime (see docker-compose.yml); the COPY here
# is only used if someone runs `docker build` standalone.
COPY . /app

EXPOSE 7787

# Healthcheck hits /ready which only returns 200 when MongoDB pings.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:7787/ready || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7787", "--reload"]
