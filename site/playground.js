const $ = (id) => document.getElementById(id);
const source = $("source");
const input = $("stdin");
const select = $("example");
const output = $("output");
const error = $("error");
const status = $("runtime-status");
const EXECUTION_TIMEOUT = 10_000;
const LOAD_TIMEOUT = 60_000;
let examples = [];
let current;
let worker;
let active;
let timer;
let requestId = 0;

function controls(busy) {
  for (const id of ["run", "check", "reset", "download", "example"]) {
    $(id).disabled = busy || !current;
  }
  source.disabled = input.disabled = !current;
  source.readOnly = input.readOnly = busy;
  $("stop").hidden = !busy;
  document.querySelector(".playground").classList.toggle("busy", busy);
}

function resetOutput() {
  output.textContent = "Run the example to see its output.";
  output.classList.add("output-placeholder");
  error.textContent = "";
  error.hidden = true;
  $("elapsed").textContent = "CONSOLE";
}

function loadExample(id, updateHash = false) {
  if (active) return;
  current = examples.find((item) => item.id === id) || examples[0];
  select.value = current.id;
  source.value = current.source;
  input.value = current.input;
  $("input-details").open = Boolean(current.input);
  $("source-name").textContent = `${current.id}.ten`;
  $("example-description").textContent = current.description;
  resetOutput();
  status.textContent = worker ? "Ready" : "Ready · runtime loads on first run";
  controls(false);
  if (updateHash) {
    const url = new URL(location.href);
    url.hash = `example=${current.id}`;
    history.replaceState(null, "", url);
  }
}

function finish() {
  clearTimeout(timer);
  active = undefined;
  controls(false);
}

function terminate(message) {
  worker?.terminate();
  worker = undefined;
  finish();
  output.classList.remove("output-placeholder");
  output.textContent = "";
  error.textContent = message;
  error.hidden = false;
  status.textContent = "Stopped · ready to run again";
  $("elapsed").textContent = "STOPPED";
}

function createWorker() {
  const instance = new Worker(new URL("./worker.js", import.meta.url));
  instance.onmessage = ({ data }) => {
    if (worker !== instance || data.id !== active?.id) return;
    if (data.type === "started") {
      clearTimeout(timer);
      status.textContent = active.checkOnly ? "Checking…" : "Running…";
      timer = setTimeout(
        () =>
          terminate(
            "Stopped after 10 seconds. Try a smaller input or range, then run again.",
          ),
        EXECUTION_TIMEOUT,
      );
    } else if (data.type === "result") {
      const checkOnly = active.checkOnly;
      output.textContent =
        data.output || (data.ok ? "Program finished without output." : "");
      output.classList.toggle("output-placeholder", data.ok && !data.output);
      error.textContent = data.error;
      error.hidden = !data.error;
      $("elapsed").textContent = `${Math.round(data.elapsed)} ms`;
      status.textContent = data.ok
        ? checkOnly
          ? "Check passed · nothing executed"
          : "Finished"
        : "Needs attention · see diagnostic above";
      finish();
    } else if (data.type === "failure") {
      terminate(data.error);
      status.textContent = "Could not load · try again";
    }
  };
  instance.onerror = (event) => {
    if (worker !== instance) return;
    event.preventDefault();
    terminate(
      "The browser runtime could not start or stopped unexpectedly. Check your connection and try again.",
    );
  };
  return instance;
}

function run(checkOnly = false) {
  if (active || !current) return;
  if (source.value.length > 100_000 || input.value.length > 20_000) {
    error.textContent =
      "Use at most 100,000 source characters and 20,000 input characters.";
    error.hidden = false;
    status.textContent = "Input is too large";
    return;
  }
  active = { id: ++requestId, checkOnly };
  controls(true);
  output.textContent = "";
  output.classList.remove("output-placeholder");
  error.textContent = "";
  error.hidden = true;
  $("elapsed").textContent = "WORKING";
  status.textContent = worker
    ? "Preparing…"
    : "Preparing runtime… first run may take a moment";
  timer = setTimeout(
    () =>
      terminate(
        "The runtime took too long to load. Check your connection and run again.",
      ),
    LOAD_TIMEOUT,
  );
  try {
    worker ??= createWorker();
    worker.postMessage({ ...active, source: source.value, input: input.value });
  } catch {
    terminate(
      "This browser could not start the playground. Try a current browser with WebAssembly and Web Worker support.",
    );
  }
}

$("run").addEventListener("click", () => run());
$("check").addEventListener("click", () => run(true));
$("stop").addEventListener("click", () =>
  terminate("Stopped. Run again to start a fresh program."),
);
$("reset").addEventListener("click", () => loadExample(current.id));
select.addEventListener("change", () => loadExample(select.value, true));
source.addEventListener("keydown", (event) => {
  if (
    (event.ctrlKey || event.metaKey) &&
    event.key === "Enter" &&
    !event.isComposing
  ) {
    event.preventDefault();
    run();
  }
});
$("download").addEventListener("click", () => {
  const url = URL.createObjectURL(
    new Blob([source.value], { type: "text/plain;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${current.id}.ten`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.querySelectorAll("[data-example]").forEach((link) => {
  link.addEventListener("click", (event) => {
    if (!examples.length || active) return;
    event.preventDefault();
    loadExample(link.dataset.example, true);
    $("playground").scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
    source.focus({ preventScroll: true });
  });
});
$("swap").addEventListener("click", () => {
  const first = $("argument-a");
  const second = $("argument-b");
  if (first.nextElementSibling === second) first.before(second);
  else second.before(first);
});
window.addEventListener("hashchange", () => {
  const id = new URLSearchParams(location.hash.slice(1)).get("example");
  if (id && examples.some((item) => item.id === id)) loadExample(id);
});

try {
  const response = await fetch(new URL("./examples.json", import.meta.url), {
    cache: "no-cache",
  });
  if (!response.ok) throw new Error("Example download failed");
  examples = await response.json();
  if (!examples.length) throw new Error("No examples available");
  select.replaceChildren(
    ...examples.map((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${item.title} / ${item.topic}`;
      return option;
    }),
  );
  loadExample(
    new URLSearchParams(location.hash.slice(1)).get("example") || "fibonacci",
  );
} catch {
  status.textContent = "Examples could not load";
  error.hidden = false;
  error.textContent =
    "Could not load the examples. Check your connection and reload this page.";
  $("example-description").textContent =
    "You can also find all examples on GitHub using the links below.";
}
