# Website and browser playground

The public introduction and playground live at
[c0ze.github.io/tenioha](https://c0ze.github.io/tenioha/). The language remains
version 0.7.1; this addition supplies examples and a browser interface to the
existing interpreter, without changing its semantics.

## Use it

Select any of the 18 examples, edit its source, and choose **Run code**. The
playground prints explicit output, then echoes non-unit expression results like
`--eval`. **Check** checks all bodies and imports without executing program I/O.
Use Ctrl+Enter (Command+Enter on macOS) while the editor is focused to run.
Normal Tab navigation and Japanese IME composition are preserved.

The input section supplies text for `読む`, one line per call. Greeting examples
prefill it with `Ada`. Missing input produces the normal `E_IO` diagnostic.
Each execution starts with fresh bindings; this is not a persistent REPL.
Reset restores the selected example and its input; switching examples replaces
the editor. Download saves the current source as a `.ten` file. Edits are not
automatically stored across reloads, so download anything you want to keep.
Links such as `#example=primes` select an example, without putting edited code
in the URL.

The browser supports the bundled `../lib/list.ten` and `../lib/option.ten`
imports. It does not upload or mount files from your computer. Custom modules
can be used with the local CLI. User source and input stay in the browser;
runtime assets are fetched from the site and jsDelivr, and fonts from Google
Fonts. No execution server, analytics, or account is used.

## Implementation

- `site/index.html`, `styles.css`, and `playground.js` provide the responsive
  introduction and editor. Output and diagnostics use text nodes, including
  when the program prints HTML-like strings.
- `site/worker.js` loads the pinned **Pyodide 0.29.3** runtime, installs the actual
  `tenioha/*.py` files and source libraries into its memory filesystem, and calls
  the Python adapter. Keeping Python in a worker allows the page to remain
  responsive during execution. See the [Pyodide worker documentation](https://pyodide.org/en/0.29.3/usage/webworker.html).
- `site/runner.py` calls `compile_source` and `execute`. Source is passed as a
  function argument, never interpolated into Python or JavaScript. Programs use
  `/playground/examples/playground.ten` as their filename, so relative library
  imports behave like the repository examples. See Pyodide's [memory filesystem
  documentation](https://pyodide.org/en/0.29.3/usage/file-system.html).
- `scripts/build_site.py` generates `dist/` from explicit site assets, a curated
  example catalog, and the checked-in interpreter/libraries. It preserves source
  characters and line endings. Example code and fixtures are read directly from
  `examples/`; there is no second implementation or copied algorithm source in
  the frontend. Audit files, transport state, and development files are excluded
  from the deployed artifact. The generated `dist/` directory is replaced on build.

Run and Check allow 10 seconds of execution after runtime preparation. **Stop**
terminates the worker immediately; the next run creates a new worker. The first
runtime load has a separate 60-second timeout and depends on the CDN connection.
Partial output from an interrupted worker is discarded. Completed runtime
errors preserve output written before the error; static errors produce none.
Output is capped at 64,000 characters, source at 100,000, and input at 20,000.
The browser counts source and input in UTF-16 code units: most Japanese
characters count as one, while emoji and some rare kanji count as two. The Python
adapter also enforces its limits independently using Unicode code points.
These are usability limits, not a general untrusted-code sandbox or a strict
browser memory cap. Normal language nesting and call limits also apply.

## Local development and verification

```sh
python scripts/serve_site.py
```

This builds and serves the site on `http://127.0.0.1:8765`. For a build only:

```sh
python scripts/build_site.py
```

Native tests cover the algorithms against independent expected results, the
adapter's checking/I/O/error behavior and limits, and the generated source bundle:

```sh
python -m unittest discover -s tests
```

Browser tests use Node.js 22 and the lockfile-pinned Playwright development
dependency. They download and run the real Pyodide runtime, so network access is
required. The test server starts automatically when no local server is running.

```sh
npm ci
npx playwright install chromium
npm run test:browser
```

The suite runs every bundled example, verifies imports and supplied input,
checks errors before I/O, tests Stop and timeout recovery, verifies output limits,
HTML-like output, example links, keyboard execution, download, responsive widths,
and recovery from a failed runtime fetch. Set `PLAYGROUND_URL` to a deployed site
URL (including its trailing slash) to test that deployment instead of localhost.

## GitHub Pages

`.github/workflows/pages.yml` tests Python 3.11 and 3.14, runs the Chromium suite,
builds a static artifact, and deploys it from `master`. Pull requests run the same
checks without deploying. Every external action is pinned to a commit. Pages
must use **GitHub Actions** as its publishing source. Deployment uses the official
[GitHub Pages workflow actions](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

All asset references are relative to the page or script URL, so the `/tenioha/`
project prefix works without an origin-root assumption. The site needs a current
browser with WebAssembly and Web Worker support; runtime download errors leave
the editor intact and allow retrying.
