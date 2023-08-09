FILES=*.py

.PHONY: all
all: flake8 pylint pytest

.PHONY: flake8
flake8:
	@flake8 --ignore=E501 $(FILES)

.PHONY: pylint
pylint:
	@PYTHONPATH=clean_registry/ pylint --disable=line-too-long $(FILES)

.PHONY: pytest
pytest:
	@pytest -v

.PHONY: e2e
e2e:
	@bash tests/e2e.sh
