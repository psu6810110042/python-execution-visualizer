import unittest
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.tracer import Tracer, ExecutionState, ExecutionLimitReached
from utils.serializer import Serializer


class TestTracer(unittest.TestCase):
    def setUp(self):
        self.buffer = io.StringIO()
        self.tracer = Tracer(stdout_buffer=self.buffer, max_steps=100)

    def test_tracer_initialization(self):
        self.assertEqual(self.tracer.step_count, 0)
        self.assertFalse(self.tracer.limit_reached)
        self.assertEqual(len(self.tracer.get_trace()), 0)
        self.assertIsInstance(self.tracer.serializer, Serializer)

    def test_trace_basic_assignment(self):
        code_str = "x = 10\ny = 20"

        code_obj = compile(code_str, "<string>", "exec")

        sys.settrace(self.tracer.trace)
        try:
            exec(code_obj, {})
        finally:
            sys.settrace(None)

        trace = self.tracer.get_trace()
        line_states = [s for s in trace if s.event == "line"]
        self.assertTrue(len(line_states) >= 2)

        state1 = line_states[0]
        self.assertIsInstance(state1, ExecutionState)
        self.assertEqual(state1.line_number, 1)
        self.assertEqual(state1.func_name, "<module>")

        state2 = line_states[1]
        self.assertEqual(state2.line_number, 2)
        self.assertIn("x", state2.locals)
        self.assertEqual(state2.locals["x"], 10)

    def test_trace_max_steps_limit(self):
        self.tracer.max_steps = 10

        code_str = "while True:\n    pass"
        code_obj = compile(code_str, "<string>", "exec")

        sys.settrace(self.tracer.trace)
        try:
            exec(code_obj, {})
        except ExecutionLimitReached:
            pass
        finally:
            sys.settrace(None)

        trace = self.tracer.get_trace()

        self.assertTrue(self.tracer.limit_reached)
        self.assertEqual(self.tracer.step_count, 10)
        self.assertEqual(len(trace), 10)

    def test_trace_stdout_capture(self):
        code_str = "print('Hello, Tracer!')"
        code_obj = compile(code_str, "<string>", "exec")

        import contextlib

        with contextlib.redirect_stdout(self.buffer):
            sys.settrace(self.tracer.trace)
            try:
                exec(code_obj, {})
            finally:
                sys.settrace(None)

        trace = self.tracer.get_trace()
        if trace:
            last_state = trace[-1]
            self.assertEqual(last_state.stdout, "Hello, Tracer!\n")

    def test_trace_exception_capture(self):
        code_str = "x = 1 / 0"
        code_obj = compile(code_str, "<string>", "exec")

        sys.settrace(self.tracer.trace)
        try:
            exec(code_obj, {})
        except ZeroDivisionError:
            pass
        finally:
            sys.settrace(None)

        trace = self.tracer.get_trace()
        exception_states = [s for s in trace if s.event == "exception"]

        self.assertTrue(len(exception_states) > 0)
        exc_state = exception_states[0]
        self.assertIsNotNone(exc_state.exception)
        self.assertEqual(exc_state.exception["type"], "ZeroDivisionError")

    def test_trace_function_stack(self):
        code_str = """
def inner():
    z = 3
    
def outer():
    inner()

outer()
"""
        code_obj = compile(code_str, "<string>", "exec")

        sys.settrace(self.tracer.trace)
        try:
            exec(code_obj, {})
        finally:
            sys.settrace(None)

        trace = self.tracer.get_trace()

        inner_states = [
            s for s in trace if s.func_name == "inner" and s.event == "line"
        ]
        self.assertTrue(len(inner_states) > 0)

        inner_state = inner_states[0]
        stack_names = [s["name"] for s in inner_state.stack]
        self.assertIn("outer", stack_names)
        self.assertIn("inner", stack_names)


if __name__ == "__main__":
    unittest.main()
