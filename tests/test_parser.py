import unittest
import ast
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.parser import CodeParser


class TestCodeParser(unittest.TestCase):
    def test_valid_basic_code(self):
        code = "x = 5\nprint(x)"
        tree = CodeParser.parse(code)
        self.assertIsInstance(tree, ast.AST)

    def test_valid_complex_code(self):
        code = """
def factorial(n):
    if n == 0:
        return 1
    else:
        return n * factorial(n-1)

class MyClass:
    def __init__(self, val):
        self.val = val

f = factorial(5)
obj = MyClass(f)
"""
        tree = CodeParser.parse(code)
        self.assertIsInstance(tree, ast.AST)

    def test_syntax_error_missing_colon(self):
        code = "if True\n    print('Oops')"
        with self.assertRaises(SyntaxError):
            CodeParser.parse(code)

    def test_syntax_error_unmatched_brackets(self):
        code = "my_list = [1, 2, 3"
        with self.assertRaises(SyntaxError):
            CodeParser.parse(code)

    def test_syntax_error_invalid_indentation(self):
        code = "def foo():\nprint('no indent')"
        with self.assertRaises(IndentationError):
            CodeParser.parse(code)

    def test_validate_empty_code(self):
        warnings = CodeParser.validate("")
        self.assertEqual(warnings, [])

    def test_validate_returns_warnings_list(self):
        code = "x = 1"
        warnings = CodeParser.validate(code)
        self.assertIsInstance(warnings, list)

    def test_validate_eval_detected(self):
        code = "x = eval('1 + 1')"
        warnings = CodeParser.validate(code)
        self.assertTrue(any("'eval' detected" in w for w in warnings))

    def test_validate_long_function_name(self):
        long_name = "a" * 51
        code = f"def {long_name}():\n    pass"
        warnings = CodeParser.validate(code)
        self.assertTrue(any("is too long" in w for w in warnings))

    def test_validate_syntax_error_returns_warning(self):
        code = "invalid python code"
        warnings = CodeParser.validate(code)
        self.assertTrue(any("Syntax Error" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
