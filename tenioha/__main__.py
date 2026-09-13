"""Run with python -m tenioha. No installation or third-party packages required."""

import argparse
from pathlib import Path
import sys

from . import Diagnostic, __version__, compile_source, execute
from .core import format_value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tenioha — Japanese particles in typed function calls")
    parser.add_argument("file", nargs="?", help="UTF-8 .ten program")
    parser.add_argument("-e", "--eval", metavar="SOURCE", help="evaluate source and print non-unit results")
    parser.add_argument("--check", action="store_true", help="check the whole file and every function body without executing it")
    parser.add_argument("--pure", action="store_true", help="require pure top-level statements")
    parser.add_argument("--version", action="version", version=f"Tenioha {__version__}")
    args = parser.parse_args(argv)
    if (args.file is None) == (args.eval is None):
        parser.error("supply either a file or --eval SOURCE")
    try:
        filename = "<eval>" if args.eval is not None else args.file
        text = args.eval if args.eval is not None else Path(args.file).read_text(encoding="utf-8-sig")
        program = compile_source(text, filename=filename, allow_io=not args.pure)
        if args.check:
            types = f", {len(program.types)} type(s)" if program.types else ""
            print(f"OK: {len(program.expressions)} statement(s), {len(program.definitions)} definition(s){types} checked.")
        else:
            results = execute(program)
            if args.eval is not None:
                for result in results:
                    if result is not None:
                        print(format_value(result))
    except Diagnostic as error:
        print(error.render(), file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as error:
        print(f"tenioha: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
