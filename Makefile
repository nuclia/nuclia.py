install:
	pip install -r code-requirements.txt
	pip install -r test-requirements.txt
	pip install -r requirements.txt
	pip install -e .

lint:
	black nuclia
	isort --profile=black nuclia
	flake8 nuclia
	mypy nuclia

test:
	pytest nuclia