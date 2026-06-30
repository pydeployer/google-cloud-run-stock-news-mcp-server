FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen --no-cache

COPY main.py ./
COPY news/ ./news/

ENV PORT=8080

CMD ["uv", "run", "--no-dev", "python", "main.py"]
