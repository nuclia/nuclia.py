lint:
	ruff check nuclia
	ruff format --check nuclia
	mypy nuclia

fmt:
	ruff check --fix nuclia
	ruff format nuclia

test:
	pytest nuclia/

# NOTE: --cov-append is useful for CI but it'll incrementally append on the same
# file if executed locally
test-cov:
	pytest \
		--cov=nuclia \
		--cov-config=.coveragerc \
		--cov-report=xml \
		--cov-append \
		nuclia/
