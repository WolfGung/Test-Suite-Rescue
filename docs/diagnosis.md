# Diagnosis

`tests_before/` holds ten tests a team would recognise. They pass on a fresh application, on one machine, in the order the files happen to be collected. Run them a second time against the same application and five of them fail, and go on failing for as long as nobody restarts it. Two more are decided by luck: a render that outran the sleep in four of these twenty runs, and a locator that finds a button by its label — silent for as long as some button carries that label, thirty seconds of waiting the moment none does. In the series this page is pinned to, that happened once.

This document takes the suite apart one disease at a time. Each section says what a reader sees, why it happens, what replaced it in `tests_after/`, and which number in `measurements/latest.json` moved. The per-test counts quoted here are read back out of that file by `tests_repo/test_readme_numbers.py`, so a re-measurement cannot leave this page behind.

Every block of output below is from a recorded series of the sick suite against one application that was started once and never restarted between runs — the condition a shared stand gives a suite. Unless a block says otherwise it is from the series `measurements/latest.json` records; the run each one comes from is named where it matters.

## Fixed sleep

**Symptom.** None a reader can point at: a sleeping test does not fail, it waits. This is run 1, the quiet afternoon the suite was written on; one test did fail in it, and it is not one of the six sleeps — it is the race of the next section:

```
......F...                                                               [100%]
```

`tests_before/test_ui_before.py::test_form_creates_task` fails in 0 of 20 runs and pays two seconds for it on every one of them. Slowness has no stack trace, which is why it survives review.

**Why.** A sleep is a guess about someone else's machine. To be right it has to be longer than the slowest render anyone will ever see, so every run pays the worst case even when the page was ready in a tenth of it. Shorten it and the test becomes flaky; lengthen it and the suite becomes slower. No value is both fast and correct, because the thing being waited for is an event, not a duration.

The cost is one addition a reader can do by hand. Six sleeps stand in the sick browser file, and of everything a sick run spends, the sleeps alone are 6.4 s (2.0 + 2.0 + 4 × 0.6) — paid on every run, whether the renders took 100 ms or 700. `tests_repo/test_docs.py` adds up the `time.sleep(…)` literals in `tests_before/` and refuses a sentence that states a different number.

**Cure.** `tests_after/ui/board.py` waits for the event. `BoardPage._wait_loaded()` asks the driver for the list's `data-loaded="true"` through `Browser.wait_for_attribute`, so a test continues the moment the render has happened and fails after ten seconds if it never does — `tests_after/test_ui.py::test_the_form_creates_a_task_that_the_board_then_shows` is the same check as the sick form test, without a sleep.

**What it changed.** Mean time per test, 0.86 s before and 0.42 s after; 109.0 s against 172.3 s for twenty runs, and the cured suite is doing three more checks per run while it saves that time. One subtraction the reader should make before crediting all of that gap to the sleeps: the sick total also holds the single thirty-second locator timeout the brittle-selector section describes — a coincidence of that series, not a sleep — so the sleeps' own share of the gap is smaller than the headline, and the per-test mean carries the same caveat. The sum of the sleeps above is the honest number; the totals are what the runs cost.

## Render race

**Symptom.** One run in five, a test that passed a minute ago:

```
>       assert page.locator("ul.task-list li").count() >= 1
E       AssertionError: assert 0 >= 1
E        +  where 0 = count()
```

**Why.** `GET /board` serves an empty list and a script that fetches the tasks after a pause the server draws between 100 ms and 700 ms (`RENDER_DELAY_DEFAULT_MS` in `app/main.py`, `app/static/board.js`). A 0.6 s sleep is right while the pause is short and wrong when it is long. Nothing about the test differs between the run that passes and the run that fails, which is exactly why such a failure gets blamed on the environment and re-run.

The arithmetic is deliberate and disclosed: a pause drawn uniformly from 100–700 ms exceeds 600 ms about one board read in six, so a 0.6 s sleep is wrong about one time in six by design. The range is not a hidden knob — it is a constant in the application, an environment variable a reader can change, and a field every measurement records, printed in the README's provenance line. A suite whose flakiness has a known rate is the only kind you can measure a cure against.

**Cure.** The same `data-loaded` wait for a page's first render. For a render that follows a click there is a second wait, because `data-loaded` was already `"true"` before the click and waiting for it again can be satisfied by the render that came before: `BoardPage.toggle_first()` reads the `data-render` counter, clicks, and waits for `before + 1`, a value the page cannot already have had. `tests_after/test_ui.py::test_toggling_marks_the_task_done_and_offers_undo` uses it.

**What it changed.** `tests_before/test_ui_before.py::test_board_lists_the_task` fails in 4 of 20 runs — one of the two tests in the "tests that fail some runs (flaky)" column, and the one that fails for this reason; the other is the locator timeout of the *Brittle selector* section. The cured suite's column reads 0, and the delay in the application was not touched.

## Order dependence

**Symptom.** Two tests fail with a message about a list:

```
>       assert any(task["id"] == created_ids[0] for task in tasks)
E   IndexError: list index out of range

>       response = api.patch(f"/api/tasks/{created_ids[0]}")
E       IndexError: list index out of range
```

**Why.** `created_ids` is a module-level list that `test_create_task` appends to and two later tests read. Top to bottom against a fresh application it works. Against an application that already holds the task, the create is refused, the list stays empty, and the readers raise `IndexError` — a message about Python, not about the board. Selecting one test with `-k` does the same thing. Nothing in either signature says it needs another test to have run first.

`tests_before/test_ui_before.py::test_board_shows_owner_in_second_column` fails in 0 of 20 runs and is order-dependent all the same: its value can never diverge, because every task on this board is owned by "pavel". What it depends on is the locator resolving at all — that is, on some earlier test having left a first row for `//ul/li[1]` to find.

**Cure.** Every cured test creates what it asserts on, in its own body, from fixtures that hand it a client and a title: `tests_after/test_api.py::test_toggling_marks_a_task_done_and_back` creates its task, toggles it twice, and asserts both states. Run it alone, first, or last and it behaves the same.

**What it changed.** Two of the five in "tests that fail every run after the first": `tests_before/test_api_before.py::test_list_contains_created_task` fails in 19 of 20 runs, and `tests_before/test_api_before.py::test_toggle_marks_done` fails in 19 of 20 runs.

## Shared state

**Symptom.** Five failures in one run, in two files, from one cause:

```
.FFFF....F                                                               [100%]
=========================== short test summary info ============================
FAILED tests_before/test_api_before.py::test_create_task - assert 409 == 201
FAILED tests_before/test_api_before.py::test_list_contains_created_task - Ind...
FAILED tests_before/test_api_before.py::test_toggle_marks_done - IndexError: ...
FAILED tests_before/test_api_before.py::test_board_has_exactly_one_task - Ass...
FAILED tests_before/test_ui_before.py::test_nothing_else_on_the_board - Asser...
```

**Why.** Three things are shared here, and only the first is visible in the test file: a module-level list inside the process, one browser page for the whole session, and the board itself — shared not only between the tests of one run but with every run that came before. The API file's toggle test flips the one task on the board, and the browser file, collected after it, meets a board whose only button already says "Undo".

**Cure.** `tests_after/conftest.py` makes the sharing deliberate. `api` and `board` are function-scoped; `unique_title` gives each test data of its own; the autouse `clean_board` resets the board before every test; and the application is the suite's own, started on a free port unless `APP_URL` names one, so a run cannot share a board with a stranger. `tests_after/test_ui.py::test_the_board_is_empty_when_nothing_was_created` only holds if that reset is real. The browser stays session-scoped — starting one per test would be the expensive kind of isolation — but no test reads anything the last one left in it.

**What it changed.** All five of "tests that fail every run after the first", before; 0 after. The cured suite's twenty runs, against an application that was never restarted, produced 0 failing runs.

## Brittle selector

**Symptom.** Almost always none. When it does show, it is thirty seconds of waiting and a message that names a locator and nothing else. The block below is from run 18 of the series taken on a developer machine on 2026-09-22 — the one this page was first pinned to; a series in which the coincidence described under it never happens shows no such output, and the locator is no less brittle for it:

```
>       page.locator("text=Done").first.click()
E       playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.
E         - waiting for locator("text=Done").first
```

What happened in that run is worth following, because nothing in the message points at it. `FORM_TITLE` is drawn once per process from four digits — about one collision in a twenty-run series — and in run 18 of that series it drew a title an earlier run had already created; the form's create was refused, the board did not grow (`assert 18 == 2`, the same count run 17 ended on), and every task standing on it had already been toggled done by the run that created it. A done task's button reads "Undo". So `text=Done` matched nothing at all and spent the full timeout proving it — while the application was answering every request correctly. `tests_before/test_ui_before.py::test_toggle_marks_done` fails in 1 of 20 runs, and that is the whole of its contribution to the measurement.

**Why.** The lesson is the nineteen runs, not the one. A brittle locator is silent until the markup — or the state the markup shows — moves. Five locators in the sick browser file address the page by its shape or its wording: `//form//input[1]`, `//form//input[2]`, `//ul/li[1]/span[2]`, `text=Create`, `text=Done`. Four of them never failed once in twenty runs, and the fifth needed a one-in-fifty coincidence to say anything. They are not costing anything today; they are a bill the next change to the page presents. Add a field at the top of the form and `//form//input[1]` fills the wrong box without complaining. Add a column and `//ul/li[1]/span[2]` reads the wrong owner, still without complaining. Rename the button to "Complete" and both text locators wait out a timeout naming nothing but a locator. The label is the worst of them, because it is not markup at all but a state: "Done" is the button of a task that is *not* done, so the locator addresses the page by the very thing the test is trying to change.

**Cure.** Every element the cured suite touches carries a `data-testid`, and both drivers look up nothing else (`tests_after/ui/browser.py`). Locator for locator: `//form//input[1]` → `title-input`, `//form//input[2]` → `owner-input`, `text=Create` → `create-button`, `//ul/li[1]/span[2]` → `task-owner`, `text=Done` → `task-toggle`. Each name says what the element is for, not where it sits or what it currently reads, so reordering the form, adding a column or relabelling the button moves none of them — and `task-toggle` is the same handle whether the button says "Done" or "Undo", which is why the cured toggle test can assert on the label instead of hunting for it. The page object names flows rather than paths: `board.owners()`, `board.titles()`, `board.first_toggle_label()`. `tests_after/test_ui.py::test_the_board_names_the_owner_next_to_the_title` reads the owner by its test id and survives any rearrangement of the row.

**What it changed.** Almost nothing in the table, and that is the point: a run or two in a series, or none at all, is all this disease is willing to show for itself while the page stands still. A brittle locator has no number until the day the page changes, and on that day it produces the least useful failure in testing — a timeout that names a locator, in a suite that is watching an application which is working perfectly.

## Hard-coded data

**Symptom.** From the second run against one application, every time:

```
>       assert response.status_code == 201
E       assert 409 == 201
```

**Why.** The title is the literal `"Write the report"`, and a title is unique in the store by rule (`app/store.py`). The first run creates it; every run after it is refused. The test is correct exactly once in the life of the application, and a team meets that as "you have to restart the stand before the tests" — a sentence that sounds like infrastructure and is really a test holding a constant where it needs a value of its own.

**Cure.** The `unique_title` fixture in `tests_after/conftest.py` returns `Write the report <8 hex characters>`, so no run can collide with an earlier one or with itself: `tests_after/test_api.py::test_a_task_can_be_created`. The store's rule is then worth a test of its own rather than an accident — `tests_after/test_api.py::test_a_duplicate_title_is_refused_with_409` creates the collision on purpose and asserts the 409.

**What it changed.** `tests_before/test_api_before.py::test_create_task` fails in 19 of 20 runs. It is the head of the group the first run breaks: its failure leaves `created_ids` empty, which is what the two order-dependent tests then trip over.

## No cleanup

**Symptom.** A count that grows by one with every run — `assert 2 == 1`, then `assert 3 == 1`, then `assert 4 == 1`:

```
>       assert len(api.get("/api/tasks").json()) == 1
E       AssertionError: assert 3 == 1
E        +  where 3 = len([{'id': 1, 'title': 'Write the report', ...}, {'id': 2, ...}, {'id': 3, ...}])
```

**Why.** Nothing in the sick suite deletes a task or resets the board. The only thing that cleans up after it is restarting the application. Two of its tests count rows, and a count is only ever right on a board nobody has used before — including the suite's own earlier runs.

**Cure.** The autouse `clean_board` fixture posts `/api/reset` before every test, and the assertions stop counting: `tests_after/test_api.py::test_the_list_holds_exactly_what_this_test_created` compares the whole list with the one id it created, so a leftover would be named in the failure rather than summed into it. The cured suite also exercises the removal path it needs — `tests_after/test_api.py::test_deleting_removes_the_task`.

**What it changed.** The other two of the five: `tests_before/test_api_before.py::test_board_has_exactly_one_task` fails in 19 of 20 runs, and `tests_before/test_ui_before.py::test_nothing_else_on_the_board` fails in 19 of 20 runs. Both pass in the first run and never again.

## Silent assert

**Symptom.** A pass. In the run above, the ninth character is the browser file's toggle test, which asserts `"Undo" in page.content()` — a substring of the whole page. Once the board holds more than one task, a row left behind by an earlier run already says "Undo", and the assertion is satisfied by a task this test never clicked. Its docstring names the two diseases it does carry, a brittle selector and a fixed sleep; what it cannot say, because nothing inside it knows, is that its assertion cannot tell the click it made from a row it never touched.

Run 18 of the measurement has the other half of the same illness. The form test's create was refused there — the title it drew had been used by an earlier run — and the test passed anyway, because `assert FORM_TITLE in page.content()` is satisfied by the refusal page, which helpfully echoes the rejected title back into the form field. `tests_before/test_ui_before.py::test_form_creates_task` — the test the *Fixed sleep* section counts at zero failures in twenty runs — passed in that run while the thing it is named after had not happened.

And when a silent assert does fail, it says only this:

```
E       assert 409 == 201
```

**Why.** An assertion that compares two numbers, or looks for a word anywhere in a document, does not record what was expected of what. `tests_before/test_api_before.py::test_health` fails in 0 of 20 runs; on the day it does fail, its message will be two status codes and no URL. The cost is not the failure, it is the half hour spent reconstructing what the test meant.

**Cure.** Assertions in `tests_after` carry the value they saw — `assert response.status_code == 409, f"a second task with the same title must be refused, got {response.status_code}"` — and the browser assertions read one element by test id instead of the page: `tests_after/test_ui.py::test_toggling_marks_the_task_done_and_offers_undo` asserts `board.first_toggle_label() == "Undo"`, the label of the button of the task it just toggled, which no other row can supply. The cured form test asserts the board's titles are exactly the one it created, so a refusal cannot read as a success.

**What it changed.** No number in the table, and that is the point of keeping it last. A silent assert costs nothing until something breaks; then it costs the one thing a suite exists to give — an answer. Three of the sick suite's tests never fail at all, and two of them cannot fail for the reason they claim to be testing: the owner test reads a value that is "pavel" on every task the board has ever held, and the form test, as run 18 showed, passes on the page that tells it no. `tests_repo/test_readme_numbers.py` counts the tests the measurement recorded at zero failures and refuses this sentence if it states another number.
