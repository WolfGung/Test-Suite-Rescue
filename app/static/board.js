// The board renders after a pause the server chose for this page load. The
// pause is the point: a test that waits for data-loaded="true" is stable, a
// test that sleeps a fixed time is stable only when the pause is shorter.
//
// data-loaded only ever says "a render happened", and a page's first render
// can already leave it "true" before any action runs — so waiting for it
// again after a click cannot tell that render from the one still to come.
// data-render is the counter a test reads before the click and waits to see
// incremented by exactly one: "the render after my click" is unambiguously
// before + 1, never confusable with the render before it.
(function () {
  const list = document.getElementById("tasks");
  const empty = document.querySelector("[data-testid='board-empty']");
  const delay = Number(list.dataset.delay || 0);

  function render(tasks) {
    list.innerHTML = "";
    empty.hidden = tasks.length > 0;
    for (const task of tasks) {
      const li = document.createElement("li");
      li.dataset.testid = "task";
      li.dataset.id = String(task.id);
      if (task.done) li.classList.add("done");
      const title = document.createElement("span");
      title.className = "title";
      title.dataset.testid = "task-title";
      title.textContent = task.title;
      const owner = document.createElement("span");
      owner.className = "owner";
      owner.dataset.testid = "task-owner";
      owner.textContent = task.owner;
      const toggle = document.createElement("button");
      toggle.dataset.testid = "task-toggle";
      toggle.textContent = task.done ? "Undo" : "Done";
      toggle.addEventListener("click", function () {
        list.dataset.loaded = "false";
        fetch("/api/tasks/" + task.id, { method: "PATCH" }).then(load);
      });
      li.append(title, owner, toggle);
      list.appendChild(li);
    }
    list.dataset.render = String(Number(list.dataset.render || 0) + 1);
    list.dataset.loaded = "true";
  }

  function load() {
    window.setTimeout(function () {
      fetch("/api/tasks").then(function (r) { return r.json(); }).then(render);
    }, delay);
  }

  load();
})();
