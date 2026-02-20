.PHONY: local setup run stop destroy assets check-requirements help

# ─── Configurable ─────────────────────────────────────────────────────────────
PYTHON         := python3.11
REQUIRED_PYTHON := 3.11
VENV          := .venv
REQUIRED_NODE := 18
REQUIRED_DOCKER := 20
INVENIO_CLI   := invenio-cli
# ──────────────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  make local     — full check + start (use this every day)"
	@echo "  make setup     — first-time setup (run once after cloning or after destroy)"
	@echo "  make run       — start services + app (skips checks, assumes setup is done)"
	@echo "  make stop      — stop services (data is preserved)"
	@echo "  make destroy   — destroy services and volumes (data is LOST)"
	@echo "  make assets    — rebuild frontend assets after CSS/JS changes"
	@echo "  make check     — verify that all required tools are installed"
	@echo ""

# ─── Daily entry point ────────────────────────────────────────────────────────
# Run this every time you want to start the application.
local: check-requirements _ensure-deps
	@echo ""
	@echo "✓ All checks passed. Starting services and application..."
	@echo ""
	$(INVENIO_CLI) services start
	$(INVENIO_CLI) run

# ─── First-time setup ─────────────────────────────────────────────────────────
setup: check-requirements
	@echo ""
	@echo "→ Installing Python and JavaScript dependencies..."
	$(INVENIO_CLI) install --pre --development
	@echo ""
	@echo "→ Setting up Docker services (DB, OpenSearch, Redis, RabbitMQ)..."
	$(INVENIO_CLI) services setup -N -f
	@echo ""
	@echo "→ Starting services..."
	$(INVENIO_CLI) services start
	@echo ""
	@echo "→ Starting application..."
	$(INVENIO_CLI) run

# ─── Start only (no checks, assumes setup is done) ────────────────────────────
run:
	$(INVENIO_CLI) services start
	$(INVENIO_CLI) run

# ─── Stop (data preserved) ────────────────────────────────────────────────────
stop:
	$(INVENIO_CLI) services stop

# ─── Destroy (data LOST) ──────────────────────────────────────────────────────
destroy:
	@echo "WARNING: this will destroy all data (DB, OpenSearch, Redis, RabbitMQ)."
	@read -p "Are you sure? [y/N] " ans && [ "$$ans" = "y" ] || (echo "Aborted."; exit 1)
	$(INVENIO_CLI) services destroy

# ─── Rebuild frontend assets ──────────────────────────────────────────────────
assets:
	. $(VENV)/bin/activate && $(INVENIO_CLI) assets build

# ─── Prerequisite checks ──────────────────────────────────────────────────────
check-requirements: _check-python _check-node _check-docker _check-invenio-cli

_check-python:
	@echo "→ Checking Python..."
	@$(PYTHON) --version > /dev/null 2>&1 || \
		(echo "✗ '$(PYTHON)' not found. Install Python $(REQUIRED_PYTHON).x via pyenv: pyenv install $(REQUIRED_PYTHON) && pyenv local $(REQUIRED_PYTHON)" && exit 1)
	@py_ver=$$($(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"); \
	if [ "$$py_ver" != "$(REQUIRED_PYTHON)" ]; then \
		echo "✗ Python $$py_ver found but $(REQUIRED_PYTHON).x is required."; \
		exit 1; \
	fi
	@echo "  ✓ $$($(PYTHON) --version)"

_check-node:
	@echo "→ Checking Node.js..."
	@node --version > /dev/null 2>&1 || \
		(echo "✗ node not found. Install via nvm: nvm install $(REQUIRED_NODE) && nvm use $(REQUIRED_NODE)" && exit 1)
	@node_ver=$$(node -e "process.stdout.write(process.versions.node.split('.')[0])"); \
	if [ "$$node_ver" -lt "$(REQUIRED_NODE)" ]; then \
		echo "✗ Node.js $$node_ver found but $(REQUIRED_NODE)+ is required. Run: nvm install $(REQUIRED_NODE) && nvm use $(REQUIRED_NODE)"; \
		exit 1; \
	fi
	@echo "  ✓ $$(node --version)"

_check-docker:
	@echo "→ Checking Docker..."
	@docker info > /dev/null 2>&1 || \
		(echo "✗ Docker is not running. Start Docker Desktop and retry." && exit 1)
	@docker_ver=$$(docker version --format '{{.Client.Version}}' 2>/dev/null | cut -d. -f1); \
	if [ "$$docker_ver" -lt "$(REQUIRED_DOCKER)" ]; then \
		echo "✗ Docker $$docker_ver found but $(REQUIRED_DOCKER)+ is required."; \
		exit 1; \
	fi
	@echo "  ✓ Docker $$(docker version --format '{{.Client.Version}}' 2>/dev/null)"

_check-invenio-cli:
	@echo "→ Checking invenio-cli..."
	@$(INVENIO_CLI) --version > /dev/null 2>&1 || \
		(echo "✗ invenio-cli not found. Install it: pip install invenio-cli" && exit 1)
	@echo "  ✓ $$($(INVENIO_CLI) --version)"

# ─── Internal helpers ─────────────────────────────────────────────────────────
_ensure-deps:
	@if [ ! -f "$(VENV)/bin/invenio" ]; then \
		echo "→ Dependencies not installed. Running invenio-cli install..."; \
		$(INVENIO_CLI) install --pre --development; \
	fi
