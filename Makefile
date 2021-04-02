test:
	@pylint *.py --disable=line-too-long
	@flake8 --ignore=E501

upload-pypi:
	@python3 setup.py sdist bdist_wheel
	@python3 -m twine upload dist/*

clean:
	@rm -rf dist/ build/ *.egg-info
