.PHONY: install dev start package benchmark reset docker-up docker-down

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env

dev:
	$(VENV)/bin/uvicorn app.main:app --reload --port 8081

start:
	./start.sh

package:
	./package.sh

benchmark:
	./scripts/benchmark.sh

reset:
	rm -rf data/chroma data/uploads data/metadata.db

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
