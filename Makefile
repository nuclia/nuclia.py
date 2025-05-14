lint:
	uv run ruff check nuclia
	uv run ruff format --check nuclia
	uv run mypy nuclia

fmt:
	uv run ruff check --fix nuclia
	uv run ruff format nuclia

test:
	uv run mypy nuclia
	uv run pytest --asyncio-mode=auto nuclia
