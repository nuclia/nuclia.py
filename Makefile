lint:
	ruff check nuclia
	ruff format --check nuclia
	mypy nuclia

fmt:
	ruff check --fix nuclia
	ruff format nuclia

test:
	pytest nuclia/

# TODO: don't leave this -k here!
test-cov:
	pytest  --cov=nuclia/ --cov-config=.coveragerc --cov-report=xml nuclia/ -k conversation
