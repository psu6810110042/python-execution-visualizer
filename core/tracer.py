from utils.serializer import Serializer


class Tracer:
    def __init__(self, stdout_buffer=None, max_steps=10000):
        self.trace_data = []
        self.serializer = Serializer()
        self.stdout_buffer = stdout_buffer
        self.line_counts = {}
        self.max_steps = max_steps
        self.step_count = 0
        self.limit_reached = False
