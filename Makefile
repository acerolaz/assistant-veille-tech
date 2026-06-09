.PHONY: up down logs install migrate migrate-down test fmt lint typecheck ingest scrape chat-test fresnews

install:
	uv sync

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

migrate:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

test:
	uv run pytest -v

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .

typecheck:
	uv run mypy app

ingest:
	PYTHONPATH=. uv run python scripts/ingest_cli.py news --topic python --topic javascript --topic ai-ml --topic devops --topic web

fresnews:
	PYTHONPATH=. uv run python scripts/fresnews.py

scrape:
	PYTHONPATH=. uv run python scripts/ingest_cli.py scrape --url https://techcrunch.com/2026/06/04/apple-approves-poke-as-the-first-ai-agent-on-its-messages-for-business-platform/

chat-test:
	curl -s -X POST http://localhost:8000/chat \
		-H 'Content-Type: application/json' \
		-d '{"question":"Quelles tendances reviennent cette semaine ?","topics":["Python","AI/ML"]}' \
		| python -m json.tool