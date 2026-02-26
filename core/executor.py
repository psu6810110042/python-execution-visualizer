import sys
import io
import contextlib
import threading
import time

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
        
        # dynamic input handling
        self.waiting_for_input = False
        self._input_event = threading.Event()
        self._current_input_value = ""
        self._run_thread = None

    def provide_input(self, value: str):
        """Called by the UI to supply the input value and unblock the executor."""
        self._current_input_value = value
        self._input_event.set()

    def stop(self):
        """Called by the UI (e.g., Ctrl+C) to terminate execution early."""
        if hasattr(self, '_stop_event'):
            self._stop_event.set()
        if getattr(self, 'tracer', None):
            self.tracer.limit_reached = True
        if getattr(self, 'waiting_for_input', False):
            self.provide_input("") # Unblock the wait to let it crash out

    def execute(self):
        CodeParser.parse(self.code)

        stdout_capture = io.StringIO()
        self._stop_event = threading.Event()
        self.tracer = Tracer(stdout_buffer=stdout_capture, max_steps=self.max_steps, stop_event=self._stop_event)
        exec_globals = {}

        def mock_input(prompt=""):
            stdout_capture.write(prompt)
            if self.inputs:
                value = str(self.inputs.pop(0))
            else:
                # Block and wait for dynamic UI input
                self.waiting_for_input = True
                self._input_event.clear()
                # Wait for up to timeout seconds minus some buffer for the input
                self._input_event.wait(timeout=self.timeout)
                value = self._current_input_value
                self.waiting_for_input = False
                
            stdout_capture.write(value + "\n")
            return value

        exec_globals["input"] = mock_input

        result = {"error": None}

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
                result["error"] = f"{type(e).__name__}: {str(e)}"

        self._run_thread = threading.Thread(target=run_code)
        self._run_thread.start()
        
        # We cannot just join with a fixed timeout anymore if we are waiting for input.
        # So we poll the thread to see if it's done or if we've exceeded the pure execution timeout (excluding input waiting time)
        start_time = threading.Timer(0, lambda: None) # mock timer
        
        # A simple polling loop that doesn't count `waiting_for_input` time towards the timeout
        exec_time = 0.0
        while self._run_thread.is_alive():
            time.sleep(0.1)
            
            if hasattr(self, '_stop_event') and self._stop_event.is_set():
                break
                
            if not self.waiting_for_input:
                exec_time += 0.1
                if exec_time >= self.timeout:
                    break
        
        # Give the thread a moment to gracefully exit after the loop breaks
        self._run_thread.join(timeout=1.0)
        
        if self._run_thread.is_alive():
            self.tracer.limit_reached = True
            result["error"] = "ExecutionTimeout: Thread killed after timeout."

        return {
            "steps": self.tracer.get_trace(),
            "counts": self.tracer.line_counts,
            "limit_reached": self.tracer.limit_reached,
            "error": result["error"],
        }
