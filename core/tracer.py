import sys
import types
from utils.serializer import Serializer


class ExecutionLimitReached(Exception):
    pass


class ExecutionState:
    def __init__(
        self,
        line_number,
        event,
        func_name,
        stack,
        locals,
        globals,
        stdout,
        exception=None,
        line_count=0,
    ):
        self.line_number = line_number
        self.event = event
        self.func_name = func_name
        self.stack = stack
        self.locals = locals
        self.globals = globals
        self.stdout = stdout
        self.exception = exception
        self.line_count = line_count


class Tracer:
    def __init__(self, stdout_buffer=None, max_steps=10000):
        self.trace_data = []
        self.serializer = Serializer()
        self.stdout_buffer = stdout_buffer
        self.line_counts = {}
        self.max_steps = max_steps
        self.step_count = 0
        self.limit_reached = False

    def trace(self, frame, event, arg):
        if self.limit_reached:
            raise ExecutionLimitReached("Execution limit reached")

        co = frame.f_code
        filename = co.co_filename

        if filename != "<string>":
            return None

        if event not in ["line", "return", "call", "exception"]:
            return self.trace

        line_no = frame.f_lineno

        if event == "line":
            self.line_counts[line_no] = self.line_counts.get(line_no, 0) + 1

        func_name = co.co_name

        stack = []
        f = frame
        while f:
            if f.f_code.co_filename == "<string>":
                name = f.f_code.co_name
                if name != "<module>":
                    stack.append({"name": name, "frame_id": id(f)})
            f = f.f_back
        stack.reverse()

        local_vars = {}
        for k, v in frame.f_locals.items():
            if k.startswith("__"):
                continue
            local_vars[k] = self.serializer.serialize(v)

        global_vars = {}
        for k, v in frame.f_globals.items():
            if k.startswith("__"):
                continue
            if k == "CodeVisualizer" or k == "Executor":
                continue
            if isinstance(v, types.ModuleType):
                continue
            global_vars[k] = self.serializer.serialize(v)

        current_out = self.stdout_buffer.getvalue() if self.stdout_buffer else ""

        exception_info = None
        if event == "exception":
            exc_type, exc_value, tb = arg
            exception_info = {"type": exc_type.__name__, "message": str(exc_value)}

        state = ExecutionState(
            line_number=line_no,
            event=event,
            func_name=func_name,
            stack=stack,
            locals=local_vars,
            globals=global_vars,
            stdout=current_out,
            exception=exception_info,
            line_count=self.line_counts.get(line_no, 0),
        )

        self.trace_data.append(state)
        self.step_count += 1
        if self.step_count >= self.max_steps:
            self.limit_reached = True
            raise ExecutionLimitReached(
                f"Execution stopped after {self.max_steps} steps."
            )

        return self.trace

    def get_trace(self):
        return self.trace_data
