"""Browser adapter for the unchanged reference interpreter; also tested natively."""

import io
import json

from tenioha import Diagnostic, compile_source, execute
from tenioha.core import format_value

MAX_OUTPUT = 64_000
MAX_SOURCE = 100_000
MAX_INPUT = 20_000


class OutputLimit(Exception):
    pass


class LimitedOutput(io.StringIO):
    def write(self, text):
        remaining = MAX_OUTPUT - self.tell()
        super().write(text[:remaining])
        if len(text) > remaining:
            raise OutputLimit("Output stopped at 64,000 characters. Try a smaller range.")
        return len(text)


def run_playground(source, input_text="", check_only=False, filename="/playground/examples/playground.ten"):
    output = LimitedOutput()
    result = {"ok": True, "output": "", "error": ""}
    try:
        if len(source) > MAX_SOURCE or len(input_text) > MAX_INPUT:
            raise ValueError("Use at most 100,000 source characters and 20,000 input characters.")
        program = compile_source(source, filename=filename)
        if check_only:
            output.write(f"OK: {len(program.expressions)} statement(s), "
                         f"{len(program.definitions)} definition(s), {len(program.types)} type(s) checked.\n"
                         "No program code was executed.\n")
        else:
            values = execute(program, stdin=io.StringIO(input_text), stdout=output)
            # Match --eval: echo non-unit results after explicit program output.
            for value in values:
                if value is not None:
                    output.write(format_value(value) + "\n")
    except Diagnostic as error:
        result.update(ok=False, error=error.render())
    except (OutputLimit, ValueError) as error:
        result.update(ok=False, error=str(error))
    except Exception as error:
        result.update(ok=False, error=f"Runtime error ({type(error).__name__}): {error}")
    result["output"] = output.getvalue()
    return json.dumps(result, ensure_ascii=False)
