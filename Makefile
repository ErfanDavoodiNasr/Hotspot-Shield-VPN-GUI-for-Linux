.PHONY: all install-dev test test-unit test-integration test-gui test-installer test-security test-live test-docker lint typecheck coverage clean

PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest
RUFF ?= $(PYTHON) -m ruff
MYPY ?= $(PYTHON) -m mypy

all: lint typecheck test coverage

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTEST) -m "not live"

test-unit:
	$(PYTEST) tests/unit -m "not live"

test-integration:
	$(PYTEST) tests/integration -m "not live"

test-gui:
	$(PYTEST) tests/gui -m "gui and not live"

test-installer:
	$(PYTEST) tests/installer -m "installer and not live"

test-security:
	$(PYTEST) tests/security
	-$(PYTHON) -m bandit -r src -q
	-$(PYTHON) -m pip_audit

test-live:
	$(PYTEST) -m live

lint:
	$(RUFF) check src tests
	@if command -v shellcheck >/dev/null 2>&1; then shellcheck install.sh uninstall.sh; else echo "shellcheck not installed — skipped"; fi

typecheck:
	$(MYPY) src/hotspotshield_gui

coverage:
	$(PYTEST) -m "not live" --cov=hotspotshield_gui --cov-report=term-missing --cov-report=xml

test-docker:
	docker build -f docker/Dockerfile -t hotspotshield-gui:test .
	docker run --rm -e DISPLAY=:99 hotspotshield-gui:test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov dist build *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
