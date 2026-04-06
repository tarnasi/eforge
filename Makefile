.PHONY: install dev test lint build clean publish

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	python -m py_compile src/environment_forge/cli.py
	python -m py_compile src/environment_forge/vault.py
	python -m py_compile src/environment_forge/crypto.py
	python -m py_compile src/environment_forge/schema.py
	python -m py_compile src/environment_forge/loader.py

build: clean
	python -m build

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository testpypi dist/*
