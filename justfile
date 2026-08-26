set shell := ["powershell.exe", "-c"]

default:
    @just --list

install:
    poetry install

gateway:
    poetry run uvicorn gateway.main:app --host 0.0.0.0 --port 8080 --reload

backends:
    poetry run python -m mock_backends.run_all

test:
    poetry run pytest -v

test-all:
    poetry run pytest -v --cov=gateway --cov-report=term-missing
    
cov:
    poetry run pytest --cov=gateway --cov-report=term-missing

lint:
    poetry run ruff check src tests

format:
    poetry run ruff format src tests

typecheck:
    poetry run mypy src

seed-routes YAML="routes.yaml":
    poetry run python -m scripts.seed_routes_from_yaml {{YAML}}

docker-up:
    docker compose up --build

docker-down:
    docker compose down -v