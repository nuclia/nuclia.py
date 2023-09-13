install:
	pip install --upgrade pip
	pip install -r code-requirements.txt
	pip install -r test-requirements.txt
	pip install -r requirements.txt
	pip install -e .

lint:
	black nuclia
	isort --profile=black nuclia
	flake8 nuclia

test:
	mypy nuclia
	pytest nuclia
