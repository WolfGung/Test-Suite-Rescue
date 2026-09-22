.PHONY: install test test-before test-selenium app measure lint

install:
	python3 -m pip install -e ".[dev]"
	python3 -m playwright install chromium

# The cured suite and the repository's own checks, on the default driver
# (Playwright). Starts the app itself.
test:
	pytest tests_after tests_repo

# The same cured browser checks on Selenium.
test-selenium:
	UI_DRIVER=selenium pytest tests_after

# The sick suite. It is meant to fail some of the time; run it to see how.
test-before:
	pytest tests_before

app:
	uvicorn app.main:app --port 8100

# Twenty runs of each suite against one live app, then the before/after table.
measure:
	python -m tools.measure --runs 20 --update-readme

lint:
	ruff check app tools tests_after tests_before tests_repo
