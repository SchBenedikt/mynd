FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY run_app.py run_app.py
COPY backend/__init__.py backend/__init__.py
COPY backend/core backend/core
COPY backend/features backend/features

RUN mkdir -p backend/config data backend/templates

EXPOSE 5001

CMD ["python", "run_app.py"]