install:
	pip install --upgrade pip wheel
	pip install -r code-requirements.txt
	pip install -r test-requirements.txt
	pip install -r requirements.txt
	pip install -e .

lint:
	ruff check nuclia
	ruff format --check nuclia
	mypy nuclia

fmt:
	ruff format nuclia

test:
	mypy nuclia
	pytest nuclia
