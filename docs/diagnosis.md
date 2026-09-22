# Diagnosis

`tests_before/` holds ten tests a team would recognise. They pass on a fresh application, on one machine, in the order the files happen to be collected. Run them a second time against the same application and five of them fail; run them on a busy machine and a sixth joins in.

This document takes the suite apart one disease at a time. Each section says what a reader sees, why it happens, what replaced it in `tests_after/`, and which number in `measurements/latest.json` moved. The per-test counts quoted here are read back out of that file by `tests_repo/test_readme_numbers.py`, so a re-measurement cannot leave this page behind.

The output below comes from runs of the sick suite against one application that was started once and never restarted between runs — the condition a shared stand gives a suite.

## Fixed sleep

**Symptom.** None a reader can point at: a sleeping test does not fail, it waits. In this run line one test did fail, and it is not one of the six sleeps — it is the race of the next section:

```
......F...                                                               [100%]
```

`tests_before/test_ui_before.py::test_form_creates_task` fails in 0 of 20 runs and pays two seconds for it on every one of them. Slowness has no stack trace, which is why it survives review.

**Why.** A sleep is a guess about someone else's machine. To be right it has to be longer than the slowest render anyone will ever see, so every run pays the worst case even when the page was ready in a tenth of it. Shorten it and the test becomes flaky; lengthen it and the suite becomes slower. No value is both fast and correct, because the thing being waited for is an event, not a duration.

**Cure.** `tests_after/ui/board.py` waits for the event. `BoardPage._wait_loaded()` asks the driver for the list's `data-loaded="true"` through `Browser.wait_for_attribute`, so a test continues the moment the render has happened and fails after ten seconds if it never does — `tests_after/test_ui.py::test_the_form_creates_a_task_that_the_board_then_shows` is the same check as the sick form test, without a sleep.

**What it changed.** Mean time per test, 0.78 s before and 0.47 s after; 122.9 s against 156.7 s for twenty runs, and the cured suite is doing three more checks per run while it saves that time.

## Render race

**Symptom.** One run in five, a test that passed a minute ago:

```
>       assert page.locator("ul.task-list li").count() >= 1
E       AssertionError: assert 0 >= 1
E        +  where 0 = count()
```

**Why.** `GET /board` serves an empty list and a script that fetches the tasks after a pause the server draws between 100 ms and 700 ms (`app/main.py`, `app/static/board.js`). A 0.6 s sleep is right while the pause is short and wrong when it is long. Nothing about the test differs between the run that passes and the run that fails, which is exactly why such a failure gets blamed on the environment and re-run.

**Cure.** The same `data-loaded` wait for a page's first render. For a render that follows a click there is a second wait, because `data-loaded` was already `"true"` before the click and waiting for it again can be satisfied by the render that came before: `BoardPage.toggle_first()` reads the `data-render` counter, clicks, and waits for `before + 1`, a value the page cannot already have had. `tests_after/test_ui.py::test_toggling_marks_the_task_done_and_offers_undo` uses it.

**What it changed.** `tests_before/test_ui_before.py::test_board_lists_the_task` fails in 4 of 20 runs — the whole of the "tests that fail some runs (flaky)" column. The cured suite's column reads 0, and the delay in the application was not touched.

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

**Symptom.** Thirty seconds of waiting, and a message about a locator:

```
>       page.locator("text=Done").first.click()
E       playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.
E         - waiting for locator("text=Done").first
```

**Why.** Three locators in the sick browser file address the page by its shape or its wording: `//form//input[1]`, `//ul/li[1]/span[2]`, `text=Done`. Add a field to the form, swap two spans, rename the button to "Complete", and all three break while the application keeps working. The label is worse than fragile, it is a state: "Done" is shown by a task that is not done, so the locator either waits out its timeout or silently picks a different row.

**Cure.** Every element the cured suite touches carries a `data-testid`, and both drivers look up nothing else (`tests_after/ui/browser.py`). The page object names flows, not paths: `board.owners()`, `board.titles()`, `board.first_toggle_label()`. `tests_after/test_ui.py::test_the_board_names_the_owner_next_to_the_title` reads the owner by its test id and survives any rearrangement of the row.

**What it changed.** Nothing in the table on its own — a brittle locator costs nothing until the page changes, which is what makes it easy to leave in. What it removes is the class of failure that reads "timeout waiting for a locator" when the application is fine.

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

**Symptom.** A pass. In the run above, the ninth character is `tests_before/test_ui_before.py::test_toggle_marks_done`, which fails in 0 of 20 runs while asserting `"Undo" in page.content()` — a substring of the whole page. Once the board holds more than one task, a row left behind by an earlier run already says "Undo", and the assertion is satisfied by a task this test never clicked. It names a render race in its docstring and is unable to observe one.

And when a silent assert does fail, it says only this:

```
E       assert 409 == 201
```

**Why.** An assertion that compares two numbers, or looks for a word anywhere in a document, does not record what was expected of what. `tests_before/test_api_before.py::test_health` fails in 0 of 20 runs; on the day it does fail, its message will be two status codes and no URL. The cost is not the failure, it is the half hour spent reconstructing what the test meant.

**Cure.** Assertions in `tests_after` carry the value they saw — `assert response.status_code == 409, f"a second task with the same title must be refused, got {response.status_code}"` — and the browser assertions read one element by test id instead of the page: `tests_after/test_ui.py::test_toggling_marks_the_task_done_and_offers_undo` asserts `board.first_toggle_label() == "Undo"`, the label of the button of the task it just toggled, which no other row can supply.

**What it changed.** No number in the table, and that is the point of keeping it last. A silent assert costs nothing until something breaks; then it costs the one thing a suite exists to give — an answer. Three of the sick suite's tests never fail at all, and two of them cannot fail for the reason they claim to be testing.
