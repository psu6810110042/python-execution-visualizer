import sys
import io
import contextlib
import threading
from core.parser import CodeParser
from core.tracer import Tracer, ExecutionLimitReached


class ExecutionTimeout(Exception):
    pass


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
        self.tracer = None

    def execute(self):
        CodeParser.parse(self.code)
        
        stdout_capture = io.StringIO()
        self.tracer = Tracer(stdout_buffer=stdout_capture, max_steps=self.max_steps)
        exec_globals = {}

        def mock_input(prompt=""):
            stdout_capture.write(prompt)
            if self.inputs:
                value = str(self.inputs.pop(0))
            else:
                value = ""
            stdout_capture.write(value + "\n")
            return value

        exec_globals["input"] = mock_input

        result = {'error': None}

        def run_code():
            try:
                with contextlib.redirect_stdout(stdout_capture):
                    sys.settrace(self.tracer.trace)
                    try:
                        exec(self.code, exec_globals)
                    finally:
                        sys.settrace(None)
            except ExecutionLimitReached:
                pass
            except Exception as e:
                result['error'] = f"{type(e).__name__}: {str(e)}"

        thread = threading.Thread(target=run_code)
        thread.start()
        thread.join(timeout=self.timeout)

        if thread.is_alive():
            self.tracer.limit_reached = True
            result['error'] = "ExecutionTimeout: Thread killed after timeout."
            # Note: Python cannot force kill a thread easily, but we'll return what we have

        return {
            "steps": self.tracer.get_trace(),
            "counts": self.tracer.line_counts,
            "limit_reached": self.tracer.limit_reached,
            "error": result['error'],
        }
