.PHONY: install fmt lint typecheck test check run infra-up infra-down

SRC := packages/core/src services/voice-gateway/src

install:
	uv sync --all-packages
	uv run pre-commit install

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy $(SRC)

test:
	uv run pytest

check: lint typecheck test

run:
	uv run uvicorn voice_gateway.main:create_app --factory --reload --port 8000

infra-up:
	docker compose up -d --wait

infra-down:
	docker compose down