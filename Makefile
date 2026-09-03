.PHONY: install dev start package benchmark analyze-chunks eval-smoke eval-check eval-ragas export-bad-cases reset docker-up docker-down worker reset-pg-password

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env

dev:
	$(VENV)/bin/uvicorn app.main:app --reload --port 8081

worker:
	./scripts/worker.sh

start:
	./start.sh

package:
	./package.sh

benchmark:
	./scripts/benchmark.sh

analyze-chunks:
	$(PYTHON) scripts/analyze_chunks.py

eval-smoke:
	./scripts/eval_smoke.sh

eval-check:
	$(PYTHON) scripts/check_eval_baseline.py

eval-ragas:
	$(PYTHON) scripts/eval_ragas.py --dry-run

export-bad-cases:
	$(PYTHON) scripts/export_bad_cases.py

reset:
	rm -rf data/chroma data/uploads data/metadata.db

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# 在 NAS 上执行：重置 kb-postgres 密码为 .env 中 POSTGRES_PASSWORD
reset-pg-password:
	./scripts/reset-pg-password.sh
