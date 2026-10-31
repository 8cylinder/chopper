.PHONY: sync fmt lint type test check install upgrade

sync:
	uv sync

fmt:
	uv run ruff format .

lint:
	uv run ruff check --fix .

type:
	uv run mypy --strict src/

test:
	uv run pytest

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy --strict src/
	uv run pytest

install:
	uv tool install --editable --force .

upgrade:
	uv sync --upgrade
