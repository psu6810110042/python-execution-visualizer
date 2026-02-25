import sys
import io
import contextlib
import multiprocessing
from core.parser import CodeParser
from core.tracer import Tracer, ExecutionLimitReached


class ExecutionTimeout(Exception):
    pass


def _run_execution(code, inputs, max_steps, queue):
    stdout_capture = io.StringIO()
    tracer = Tracer(stdout_buffer=stdout_capture, max_steps=max_steps)
    exec_globals = {}

    def mock_input(prompt=""):
        stdout_capture.write(prompt)
        if inputs:
            value = str(inputs.pop(0))
        else:
            value = ""
        stdout_capture.write(value + "\n")
        return value

    exec_globals["input"] = mock_input

    error_msg = None
    try:
        with contextlib.redirect_stdout(stdout_capture):
            sys.settrace(tracer.trace)
            try:
                exec(code, exec_globals)
            finally:
                sys.settrace(None)
    except ExecutionLimitReached:
        pass
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"

    queue.put(
        {
            "steps": tracer.get_trace(),
            "counts": tracer.line_counts,
            "limit_reached": tracer.limit_reached,
            "error": error_msg,
        }
    )


class Executor:
    def __init__(
        self,
        code: str,
        inputs: list = None,
        timeout: float = 10.0,
        max_steps: int = 10000,
    ):
        self.code = code
        self.inputs = inputs[:] if inputs else []
        self.timeout = timeout
        self.max_steps = max_steps

    def execute(self):
        CodeParser.parse(self.code)
        
        # Use spawn context for cross-platform reliability
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()

        process = ctx.Process(
            target=_run_execution,
            args=(self.code, self.inputs, self.max_steps, queue),
        )
        process.start()
        process.join(timeout=self.timeout)

        if process.is_alive():
            process.terminate()  # Brutally kill the OS process
            process.join()       # Wait for termination
            return {
                "steps": [],
                "counts": {},
                "limit_reached": True,
                "error": "ExecutionTimeout: Process killed after timeout.",
            }

        if not queue.empty():
            return queue.get()

        return {
            "steps": [],
            "counts": {},
            "limit_reached": False,
            "error": "Unknown Execution Error: Process died unexpectedly.",
        }
