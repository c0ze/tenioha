"""Build the Pages artifact from checked-in site assets and actual interpreter files."""

import html
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tenioha import __version__
from tenioha.core import read_source


def build(destination=ROOT / "dist"):
    destination = Path(destination)
    if destination.resolve() == ROOT or destination.resolve() in ROOT.parents:
        raise ValueError("The build destination cannot replace the repository or its parents.")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in ("index.html", "styles.css", "playground.js", "worker.js", "favicon.svg"):
        text = read_source(ROOT / "site" / name)
        (destination / name).write_text(text.replace("{{VERSION}}", html.escape(__version__)), encoding="utf-8")
    catalog = json.loads((ROOT / "site/catalog.json").read_text(encoding="utf-8"))
    seen = set()
    for example in catalog:
        name = example["id"]
        if name in seen or not name.replace("_", "").isalnum():
            raise ValueError(f"Invalid or duplicate example id: {name}")
        seen.add(name)
        path = ROOT / "examples" / f"{name}.ten"
        example["source"] = read_source(path)
        example["expected"] = read_source(path.with_suffix(".out"))
        input_path = path.with_suffix(".in")
        example["input"] = read_source(input_path) if input_path.exists() else ""
    (destination / "examples.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    files = {str(path.relative_to(ROOT)): read_source(path)
             for pattern in ("tenioha/*.py", "lib/*.ten") for path in sorted(ROOT.glob(pattern))}
    files["runner.py"] = read_source(ROOT / "site/runner.py")
    (destination / "runtime.json").write_text(json.dumps({"version": __version__, "files": files}, ensure_ascii=False), encoding="utf-8")
    (destination / ".nojekyll").touch()
    return len(catalog)


if __name__ == "__main__":
    print(f"Built dist/ with {build()} examples and Tenioha {__version__}.")
