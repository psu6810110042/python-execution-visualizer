class Serializer:
    def __init__(self, max_depth=3, max_length=20):
        self.max_depth = max_depth
        self.max_length = max_length

    def serialize(self, obj):
        return self._serialize_recursive(self, obj, depth=0, seen=set())

    # private function to serialize shit
    def _serialize_recursive(self, obj, depth, seen):

        # recursively go through shit
        return
