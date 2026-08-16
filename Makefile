.PHONY: help install test solver-image list build-omgzip

help:
	@echo "targets: install, test, solver-image, list"

install:
	pip install -e '.[dev,openai]'

test:
	python3 -m pytest

# Build the agent sandbox image used by the Docker sandbox.
solver-image:
	docker build -t ctfbench/solver:latest docker/solver

list:
	python3 -m ctfbench.cli list
