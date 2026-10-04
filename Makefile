.PHONY: check test lint typecheck clean bench-tokens

check:
	./run_checks.sh

test:
	python3 -m pytest -v

bench-tokens:
	python3 -c "from procore_mcp.benchmarks import main; main()"

lint:
	ruff check .

typecheck:
	python3 -m mypy --strict procore_mcp tests

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

