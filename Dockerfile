FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 5000

CMD ["uv", "run", "gunicorn", \
    "--bind", "0.0.0.0:5000", \
    "--workers", "4", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "xmrnodes.app:app"]
