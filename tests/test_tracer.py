import unittest
import sys
import os
import io

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.tracer import Tracer
from utils.serializer import Serializer


class TestTracer(unittest.TestCase):
    def setUp(self):
        self.buffer = io.StringIO()
        self.tracer = Tracer(stdout_buffer=self.buffer, max_steps=100)

    def test_tracer_initialization(self):
        self.assertEqual(self.tracer.step_count, 0)
        self.assertFalse(self.tracer.limit_reached)
        # self.assertEqual(len(self.tracer.get_trace()), 0)
        self.assertIsInstance(self.tracer.serializer, Serializer)
