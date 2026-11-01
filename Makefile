.DEFAULT_GOAL := help
.PHONY: help setup assets backend ui web-dev web-build demo replay tidy eval-demo eval-replay sim-test test lint typecheck check

SAMPLE ?= toys_into_bin
SEED   ?= 3

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install Python and web dependencies
	uv sync
	cd web && pnpm install
	@test -f .env || cp .env.example .env

assets: ## Download the Panda model
	./scripts/fetch_assets.sh

backend: ## Run only the API on :8000 (pair with `make web-dev`)
	uv run showonce ui

ui: web-build ## Build the frontend and serve the app on :8000
	uv run showonce ui

web-dev: ## Vite dev server on :5173 (run `make backend` separately)
	cd web && pnpm dev

web-build: ## Build the frontend into web/dist
	cd web && pnpm build

demo: ## Learn a sample and run it (SAMPLE=toys_into_bin)
	uv run showonce demo samples/$(SAMPLE).mp4 --scene samples/$(SAMPLE).json

replay: ## Replay a learned program on a shuffled layout (SAMPLE, SEED)
	uv run showonce replay runs/$(SAMPLE)/program.json --scene runs/$(SAMPLE)/scene.json --seed $(SEED)

tidy: ## Tidy a scattered table with no demo (SEED)
	uv run showonce tidy samples/tidy_table.json --seed $(SEED)

eval-demo: ## Score video -> program -> robot on all samples
	uv run showonce eval-demo

eval-replay: ## Every sample x 3 shuffled layouts
	uv run showonce eval-replay

sim-test: ## 10 random block stacks, no API needed
	uv run showonce sim-test

test: ## Python and web tests
	uv run pytest
	cd web && pnpm test

lint: ## Ruff and web lint
	uv run ruff check .
	cd web && pnpm lint

typecheck: ## mypy and tsc
	uv run mypy src
	cd web && pnpm typecheck

check: lint typecheck test ## Everything CI would run
