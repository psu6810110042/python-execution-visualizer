import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.serializer import Serializer


class TestSerializer(unittest.TestCase):
    def setUp(self):
        self.serializer = Serializer(max_depth=3, max_length=5)
        self.default_serializer = Serializer()

    def test_primitives(self):
        self.assertEqual(self.serializer.serialize(None), "None")
        self.assertEqual(self.serializer.serialize(True), True)
        self.assertEqual(self.serializer.serialize(False), False)
        self.assertEqual(self.serializer.serialize(42), 42)
        self.assertEqual(self.serializer.serialize(3.14), 3.14)
        self.assertEqual(self.serializer.serialize("hello world"), "hello world")

    def test_lists_and_tuples(self):
        self.assertEqual(self.serializer.serialize([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.serializer.serialize((1, 2, 3)), [1, 2, 3])

    def test_list_truncation(self):
        long_list = [1, 2, 3, 4, 5, 6, 7]
        result = self.serializer.serialize(long_list)
        self.assertEqual(len(result), 6)
        self.assertEqual(result[:5], [1, 2, 3, 4, 5])
        self.assertEqual(result[5], "<truncated, total 7>")

    def test_sets(self):
        s = {1, 2, 3}
        result = self.serializer.serialize(s)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["__type"], "set")
        self.assertEqual(sorted(result["items"]), [1, 2, 3])

    def test_set_truncation(self):
        s = {1, 2, 3, 4, 5, 6}
        result = self.serializer.serialize(s)
        self.assertEqual(result["__type"], "set")
        self.assertEqual(len(result["items"]), 6)
        self.assertEqual(result["items"][-1], "<truncated, total 6>")

    def test_dicts(self):
        d = {"a": 1, "b": 2}
        self.assertEqual(self.serializer.serialize(d), {"a": 1, "b": 2})

    def test_dict_truncation(self):
        d = {str(i): i for i in range(10)}
        result = self.serializer.serialize(d)
        self.assertEqual(len(result), 6)
        self.assertEqual(result["__truncated"], "total 10")

    def test_circular_reference_list(self):
        l = [1, 2]
        l.append(l)
        result = self.serializer.serialize(l)
        self.assertEqual(result[:2], [1, 2])
        self.assertTrue(result[2].startswith("<Circular Reference "))

    def test_circular_reference_dict(self):
        d = {"a": 1}
        d["self"] = d
        result = self.serializer.serialize(d)
        self.assertEqual(result["a"], 1)
        self.assertTrue(result["self"].startswith("<Circular Reference "))

    # Nested 5 levels deep
    # max_depth is 3
    # Level 0: [
    # Level 1:   [
    # Level 2:     [
    # Level 3:       [
    # Level 4:         (cutoff -> lists hit type(...) string)
    def test_max_depth_recursion(self):
        nested = [[[[[1]]]]]
        result = self.serializer.serialize(nested)
        self.assertEqual(result, [[[["list(...)"]]]])

    def test_functions_and_modules(self):
        def my_test_func():
            pass

        func_res = self.serializer.serialize(my_test_func)
        self.assertEqual(func_res, "<function my_test_func>")

        mod_res = self.serializer.serialize(sys)
        self.assertEqual(mod_res, "<module sys>")

    def test_generators(self):
        def string_yielder():
            yield "a"

        gen_res = self.serializer.serialize(string_yielder())
        self.assertEqual(gen_res, "<generator string_yielder>")

    def test_bytes_and_bytearray(self):
        b = b"hello"
        self.assertEqual(self.serializer.serialize(b), "b'68656c6c6f'")

        # Test large bytes truncation
        long_b = b"x" * 60
        res = self.serializer.serialize(long_b)
        self.assertTrue(res.endswith("...' (60 bytes)"))

        ba = bytearray([1, 2, 3])
        self.assertEqual(self.serializer.serialize(ba), "bytearray([1, 2, 3])")
