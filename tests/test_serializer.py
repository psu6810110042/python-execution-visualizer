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
