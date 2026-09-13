/* A disposable worker keeps long programs away from the page's UI thread. */
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.29.3/full/";
let ready;

async function prepare() {
  const response = await fetch(new URL("./runtime.json", self.location.href), {
    cache: "no-cache",
  });
  if (!response.ok)
    throw new Error(`Could not load the interpreter (${response.status}).`);
  const bundle = await response.json();
  importScripts(`${PYODIDE_URL}pyodide.js`);
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  for (const [path, source] of Object.entries(bundle.files)) {
    const target = `/playground/${path}`;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, source, { encoding: "utf8" });
  }
  pyodide.FS.mkdirTree("/playground/examples");
  pyodide.runPython(
    "import sys\nsys.path.insert(0, '/playground')\nfrom runner import run_playground",
  );
  return pyodide.globals.get("run_playground");
}

self.onmessage = async ({ data }) => {
  const { id, source, input, checkOnly } = data;
  try {
    ready ??= prepare();
    const run = await ready;
    self.postMessage({ id, type: "started" });
    const start = performance.now();
    // Source and input are arguments, never interpolated into Python or JS code.
    const result = JSON.parse(run(source, input, checkOnly));
    self.postMessage({
      id,
      type: "result",
      ...result,
      elapsed: performance.now() - start,
    });
  } catch (error) {
    ready = undefined;
    self.postMessage({
      id,
      type: "failure",
      error: `Could not prepare the playground. ${error.message || error} Check your connection and try again.`,
    });
  }
};
