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


if __name__ == "__main__":
    unittest.main()
