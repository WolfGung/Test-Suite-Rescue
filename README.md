# Test Suite Rescue

A deliberately sick test suite, its cured version with the same coverage, and the measured difference between them — twenty runs of each against the same application, reproducible with one command.

[![CI](https://github.com/WolfGung/Test-Suite-Rescue/actions/workflows/ci.yml/badge.svg)](https://github.com/WolfGung/Test-Suite-Rescue/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A suite is rarely rewritten because someone wants tidier code. It is rewritten because the team stopped believing it: a run goes red for no reason anyone can name, so the build gets re-run instead of read. This repository is that job, done in the open — what it takes to fix flaky tests, what it takes to reduce test execution time, and what to do with a suite that needs a restart between runs. The sick suite is not a strawman: it passes on a quiet afternoon against a fresh application — the series in the table happened to lose its very first run to the render race, which is why every run there is red — and every disease in it is one that production suites carry.

## Before and after

<!-- measurements:start -->
| Measure | Before | After |
| --- | --- | --- |
| Tests per run | 10 | 13 |
| Total time for 20 runs | 146.0 s | 118.9 s |
| Mean time per test | 0.73 s | 0.46 s |
| Runs with at least one failure | 20 of 20 (100%) | 0 of 20 (0%) |
| Tests that fail every run | 0 | 0 |
| Tests that fail every run after the first | 5 | 0 |
| Tests that fail some runs (flaky) | 1 | 0 |

Measured on github-runner — Linux-6.17.0-1022-azure-x86_64-with-glibc2.39, Python 3.12.14, 2026-09-23T00:19:30+00:00; render delay 100–700 ms; 20 runs of each suite.
<!-- measurements:end -->

The numbers come from `measurements/latest.json`, which `tools/measure.py` writes: twenty runs of each suite against one application that is started once and never restarted between runs, with the board's render delay drawn from the range the file records. The line under the table is generated from that same file, so the delay range and the machine the numbers were taken on are pinned exactly like the table. The committed file is the weekly `measure` job's artifact, taken on a GitHub runner — the line under the table says so; `make measure` takes one on your machine instead, and the line then reads `developer-machine`. That hand-off is two commands and no arithmetic — `cp ci-latest.json measurements/latest.json && python3 -m tools.measure --render measurements/latest.json --update-readme`, which also prints the per-test sentences `docs/diagnosis.md` quotes, ready to paste. `make measure` takes the measurement here instead, and `tests_repo/test_readme_numbers.py` refuses a block that differs from the file, so this section cannot drift away from the measurement it describes.

Three rows are worth a sentence:

- **Tests per run** differs because curing a suite is not thinning it out. Of the sick suite's ten checks, eight survive — two of them merged into one cured test that compares the whole list with the one id it created, and the health check became the fixture's readiness probe rather than a test of its own — and five checks are new: a duplicate title refused on the form and again on the API, a missing task answering 404, a delete, and a task created through the API appearing on the board. Eight and five is the thirteen in the table; `pytest --collect-only -q tests_after` lists them.
- **Tests that fail every run after the first** is the state-pollution group. Those tests pass against a fresh application and fail against the one they polluted themselves. A team meets them as "you have to restart the stand before the tests".
- **Tests that fail some runs (flaky)** is luck, and it comes in two kinds here: a fixed sleep against a render that takes a different time on every load, and a locator that addresses a button by its label — silent until a title collision leaves no button carrying it (see [Brittle selector](docs/diagnosis.md#brittle-selector)). Which of the two a series catches, and how often, is the coin toss the row counts.

The CI `measure` job re-measures on a schedule and compares the result with the committed file within a tolerance, so numbers that quietly move are caught there rather than by a reader.

## What was sick, and the cure

| Disease | Where in `tests_before` | What replaced it in `tests_after` | Section |
| --- | --- | --- | --- |
| Fixed sleep | `time.sleep(0.6)` and `time.sleep(2.0)` after every action in `test_ui_before.py` | `BoardPage._wait_loaded()` waits for `data-loaded="true"` | [Fixed sleep](docs/diagnosis.md#fixed-sleep) |
| Render race | `test_board_lists_the_task` reads the list when the sleep ends, not when the render does | the same wait, plus the `data-render` counter for a render that follows a click | [Render race](docs/diagnosis.md#render-race) |
| Order dependence | `test_list_contains_created_task` and `test_toggle_marks_done` read `created_ids[0]` | every test creates what it asserts on, in its own body | [Order dependence](docs/diagnosis.md#order-dependence) |
| Shared state | a module-level `created_ids`, one browser page for the whole session, one board for every run | function-scoped `api` and `board` fixtures, `clean_board` before each test | [Shared state](docs/diagnosis.md#shared-state) |
| Brittle selector | `//form//input[1]`, `//ul/li[1]/span[2]`, `text=Create`, `text=Done` | `data-testid` hooks, the only thing either driver looks up | [Brittle selector](docs/diagnosis.md#brittle-selector) |
| Hard-coded data | the title `"Write the report"`, unique in the store by rule | the `unique_title` fixture | [Hard-coded data](docs/diagnosis.md#hard-coded-data) |
| No cleanup | nothing ever deletes a task or resets the board | the autouse `clean_board` fixture | [No cleanup](docs/diagnosis.md#no-cleanup) |
| Silent assert | `assert response.status_code == 201`, `"Undo" in page.content()` | assertions that carry the value they saw and read one element, not the page | [Silent assert](docs/diagnosis.md#silent-assert) |

`docs/diagnosis.md` takes each of these apart: what a reader sees, why it happens, what replaced it, and which number it moved.

## Run it

A virtualenv, then three commands:

```bash
python3 -m venv .venv && source .venv/bin/activate
make install   # dependencies, and the browser Playwright drives
make test      # the cured suite and the repository's own checks
make measure   # twenty runs of each suite, then the table above
```

`UI_DRIVER=selenium make test` runs the same browser checks on the second engine. `make test-before` starts an application of its own, runs the sick suite against it twice and takes it down again — read the second run, because that is where a board nobody cleared and a title already taken make themselves felt. `make app` serves the board on <http://127.0.0.1:8100> to look at by hand; `APP_PORT=8109 make test-before` moves both off 8100 when something else holds it.

## Docker

```bash
docker compose up -d app        # the board on http://127.0.0.1:8100
docker compose run --rm tests   # the cured suite against it
```

The test container writes its Allure results into `allure-results/` on the host, which is why its command names that directory. The image carries Chromium for Playwright only. The Selenium engine wants a Chrome of its own, so run that one on the host.

## How the repository is put together

```
app/            the application under test: a task board whose list renders after a delay
tests_before/   the sick suite: ten tests, every disease named in their own docstrings
tests_after/    the cured suite: eight of those checks, plus five the sick suite never had
  ui/           the Browser interface, the page object, and the two drivers behind them
tests_repo/     the repository's checks on itself: the table, the documents, the pipeline
tools/          measure.py, which runs both suites and writes the block; compare.py
measurements/   latest.json — the measurement this README is rendered from
docs/           diagnosis.md — one section per disease
```

## Two engines, one suite

The browser tests never touch a driver. They talk to a page object, which talks to a `Browser` interface — `goto`, `fill`, `click`, `text`, `texts`, `attribute`, `wait_for_attribute`, `wait_for_present` — and `UI_DRIVER` decides which implementation answers: `tests_after/ui/playwright_driver.py` or `tests_after/ui/selenium_driver.py`. The tests do not know which one they got, and both find elements only by `data-testid`.

This is not variety for its own sake. A suite welded to one tool is a suite that cannot be moved, and a change of engine is a change of infrastructure, not of what the product is supposed to do. The same thirteen checks run on both.

## Configuration

Four settings, and all four are read from the environment — nothing here loads a `.env` file, so set them in the shell, in the compose file, or in the CI job:

| Variable | What it does |
| --- | --- |
| `APP_URL` | Set: both suites use that address exactly as given and start nothing, which is what CI and the Docker stand do. Unset: the cured suite starts its own application on a free port, so no run shares a board with a stranger's; the sick suite simply assumes something answers on 8100, which is one of the things wrong with it. |
| `UI_DRIVER` | `playwright` (default) or `selenium`. |
| `HEADLESS` | `false` to watch the browser do the work. |
| `RENDER_DELAY_MIN_MS` / `RENDER_DELAY_MAX_MS` | The range the board draws its render delay from, the one deliberate source of timing in the application; the default is in `app/main.py` as `RENDER_DELAY_DEFAULT_MS`, and the measurement records the range it was taken with. |

## Licence

MIT — see [LICENSE](LICENSE).

## Related work

Three more repositories from the same portfolio:

- **[Toolshop-Test-Automation-Framework](https://github.com/WolfGung/Toolshop-Test-Automation-Framework)** — a test automation framework built from scratch for an online shop: API, browser and end-to-end cases against a public demo shop or a local Docker stand, with test design documents.
- **[Marketplace-Test-Automation-Framework](https://github.com/WolfGung/Marketplace-Test-Automation-Framework)** — API and browser tests for a marketplace shop, run against a small stand shipped in the repository with a nightly drift check of the public demo site, a smoke set, video and traces per browser test and a published Allure report.
- **[Web-Scraping-Automation-Framework](https://github.com/WolfGung/Web-Scraping-Automation-Framework)** — a scraper that collects two practice sites over HTTP and through a browser, detects changes between nightly runs and publishes the data, the change report and the test report.

## Hire me

I take short, well-defined jobs: a test automation framework from scratch, an API test suite for an existing backend, end-to-end tests for a critical flow, fixing flaky tests and reducing run time, setting up CI for existing tests, scrapers and data pipelines. Profile on Guru: [https://www.guru.com/freelancers/pavel-zhukov-atum](https://www.guru.com/freelancers/pavel-zhukov-atum). Time zone UTC+2; I work in writing.
