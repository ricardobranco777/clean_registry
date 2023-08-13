FILES=*.py tests/*.py

.PHONY: all
all: flake8 pylint pytest mypy

.PHONY: flake8
flake8:
	@flake8 --ignore=E501 $(FILES)

.PHONY: pylint
pylint:
	@pylint --disable=line-too-long $(FILES)

.PHONY: pytest
pytest:
	@pytest --capture=sys -v --cov --cov-report term-missing

.PHONY: mypy
mypy:
	@mypy $(FILES)

.PHONY: e2e
e2e:
	@bash tests/e2e.sh
