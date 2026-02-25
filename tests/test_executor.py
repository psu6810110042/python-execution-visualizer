import unittest
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.executor import Executor, ExecutionTimeout


class TestExecutor(unittest.TestCase):
    def test_basic_execution(self):
        code = "x = 5\ny = x * 2"
        executor = Executor(code=code)
        result = executor.execute()

        self.assertIn("steps", result)
        self.assertIn("counts", result)
        self.assertIn("limit_reached", result)

        self.assertFalse(result["limit_reached"])
        self.assertTrue(len(result["steps"]) > 0)

    def test_syntax_error_before_execution(self):
        code = "if True\n    pass"  # missing colon
        executor = Executor(code=code)

        with self.assertRaises(SyntaxError):
            executor.execute()

    def test_runtime_exception(self):
        code = "x = 1 / 0"
        executor = Executor(code=code)

        result = executor.execute()
        self.assertIsNotNone(result["error"])
        self.assertIn("ZeroDivisionError", result["error"])

    def test_execution_timeout(self):
        code = "import time\nwhile True:\n    time.sleep(0.1)"

        # Set a very short timeout
        executor = Executor(code=code, timeout=0.5)

        start_time = time.time()
        result = executor.execute()
        duration = time.time() - start_time

        self.assertTrue(duration < 2.0)

        self.assertTrue(result["limit_reached"])

    def test_step_limit(self):
        code = "while True:\n    pass"
        executor = Executor(code=code, max_steps=50, timeout=5.0)

        result = executor.execute()
        self.assertTrue(result["limit_reached"])
        self.assertEqual(len(result["steps"]), 50)

    def test_stdout_capture(self):
        code = "print('Hello from Executor!')"
        executor = Executor(code=code)

        result = executor.execute()

        final_state = result["steps"][-1]
        self.assertEqual(final_state.stdout, "Hello from Executor!\n")

    def test_mock_input(self):
        code = """
name = input("Enter name: ")
print("Hello " + name)
"""
        executor = Executor(code=code, inputs=["Alice"])
        result = executor.execute()

        final_state = result["steps"][-1]
        self.assertEqual(final_state.stdout, "Enter name: Alice\nHello Alice\n")

    def test_empty_code(self):
        executor = Executor(code="")
        result = executor.execute()
        self.assertTrue(len(result["steps"]) >= 0)


if __name__ == "__main__":
    unittest.main()
