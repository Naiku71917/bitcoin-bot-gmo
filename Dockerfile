FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY configs /app/configs

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

RUN mkdir -p /app/var/artifacts /app/var/logs

CMD ["python", "-m", "bitcoin_bot.main", "--config", "configs/runtime.example.yaml", "--mode", "live"]
