.PHONY: install test lint typecheck format ci clean execute-notebooks test-notebooks

install:
	poetry install

test:
	poetry run pytest

lint:
	poetry run ruff check src tests
	poetry run ruff format --check src tests

format:
	poetry run ruff check --fix src tests
	poetry run ruff format src tests

typecheck:
	poetry run mypy src

# execute-notebooks:
# 	poetry run jupyter nbconvert --to notebook --execute --inplace examples/*.ipynb \
# 		--ExecutePreprocessor.timeout=120

# test-notebooks:
# 	poetry run pytest --nbmake --no-cov examples/

ci: lint typecheck test

clean:
	rm -rf dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/ .ruff_cache/
