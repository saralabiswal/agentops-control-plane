.PHONY: install dev test lint typecheck migrate seed docker-up docker-down

install:
	uv sync --extra dev
	cd ../frontend && npm install

dev:
	uv run python -m uvicorn app.main:app --reload --port 8000 & cd ../frontend && npm run dev

test:
	uv run python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80

lint:
	uv run ruff check app/ tests/

typecheck:
	uv run mypy app/

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m app.seed.seed

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
