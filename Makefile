.PHONY: install test test-before test-selenium app measure compare lint

# The port `make test-before` and `make app` serve the board on. Override it
# when something else already holds 8100: APP_PORT=8109 make test-before
APP_PORT ?= 8100

install:
	python3 -m pip install -e ".[dev]"
	python3 -m playwright install chromium

# The cured suite and the repository's own checks, on the default driver
# (Playwright). Starts the app itself.
test:
	python3 -m pytest tests_after tests_repo

# The same cured browser checks on Selenium.
test-selenium:
	UI_DRIVER=selenium python3 -m pytest tests_after

# The sick suite, against one app that is started here and never restarted
# between the two runs — the same shape as the CI `before` job. The first run
# is the quiet afternoon; the second is the one to read, because the diseases
# of state (a title already taken, a board nobody cleared) only show once a
# run has been before it. The app is killed whatever happens.
test-before:
	@set -e; \
	python3 -m uvicorn app.main:app --port $(APP_PORT) --log-level warning & \
	APP_PID=$$!; \
	trap 'kill $$APP_PID 2>/dev/null || true' EXIT INT TERM; \
	for i in $$(seq 1 30); do \
		curl -fs http://127.0.0.1:$(APP_PORT)/healthz >/dev/null && break || sleep 1; \
	done; \
	echo "--- first run (a fresh board: this is the one that passes)"; \
	APP_URL=http://127.0.0.1:$(APP_PORT) python3 -m pytest tests_before -q -p no:cacheprovider || true; \
	echo "--- second run (the same board, second time: read this one)"; \
	APP_URL=http://127.0.0.1:$(APP_PORT) python3 -m pytest tests_before -q -p no:cacheprovider || true

app:
	python3 -m uvicorn app.main:app --port $(APP_PORT)

# Twenty runs of each suite against one live app, then the before/after block.
measure:
	python3 -m tools.measure --runs 20 --update-readme --taken-on developer-machine

# The committed measurement against a fresh one, within the tolerances CI uses.
compare:
	python3 -m tools.compare measurements/latest.json measurements/ci-latest.json

lint:
	ruff check app tools tests_after tests_before tests_repo
