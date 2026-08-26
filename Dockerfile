FROM python:3.12.10-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir poetry==1.8.3
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false && poetry install --no-root --only main
COPY src ./src
COPY mock_backends ./mock_backends
COPY scripts ./scripts
COPY routes.yaml routes.docker.yaml ./
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8080
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]