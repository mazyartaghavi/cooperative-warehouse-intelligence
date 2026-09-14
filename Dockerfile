FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.11
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev
RUN useradd --create-home cwi && mkdir -p /app/data/local && chown -R cwi:cwi /app/data
USER cwi
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "cwi.api.app:app_factory", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
