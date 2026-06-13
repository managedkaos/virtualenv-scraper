.PHONY: lint test build

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/
	mypy src/

test:
	pytest

build:
	@echo "Python build: no-op (interpreted language)"
