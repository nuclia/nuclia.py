lint:
	ruff check nuclia
	ruff format --check nuclia
	mypy nuclia

fmt:
	ruff check --fix nuclia
	ruff format nuclia

test:
	pytest nuclia/

test-cov:
	pytest --cov=nuclia/ --cov-config=.coveragerc --cov-report=xml nuclia/
