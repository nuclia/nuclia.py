lint:
	ruff check nuclia
	ruff format --check nuclia
	mypy nuclia

fmt:
	ruff check --fix nuclia
	ruff format nuclia

test:
	uv run mypy nuclia
	uv run pytest --asyncio-mode=auto nuclia
