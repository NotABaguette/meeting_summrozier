# Convenience commands. Run `make help` for the list.
.DEFAULT_GOAL := help
COMPOSE := docker compose
OLLAMA_MODEL ?= gemma4:e2b-it-qat

.PHONY: help up down restart logs ps pull-model test demo build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the whole stack (web UI on http://localhost:8080)
	$(COMPOSE) up -d --build
	@echo "Started. Open http://localhost:8080 (the LLM is downloading in the background)."

down: ## Stop the stack
	$(COMPOSE) down

restart: ## Restart services
	$(COMPOSE) restart

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

pull-model: ## Pre-pull the summarization model into Ollama
	$(COMPOSE) exec ollama ollama pull $(OLLAMA_MODEL)

watch: ## Start with the watch-folder ingester (drop files into ./recordings)
	$(COMPOSE) --profile watch up -d --build

test: ## Run the test suite
	cd app && python -m pytest -q

build: ## Build images only
	$(COMPOSE) build

clean: ## Stop and REMOVE all data volumes (DANGER: deletes everything)
	$(COMPOSE) down -v
