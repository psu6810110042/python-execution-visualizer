class Serializer:
    def __init__(self, max_depth=3, max_length=20):
        self.max_depth = max_depth
        self.max_length = max_length

    def serialize(self, obj):
        return self._serialize_recursive(obj, depth=0, seen=set())

    # private function to serialize objects
    def _serialize_recursive(self, obj, depth, seen):

        # recursively go through the object
        obj_id = id(obj)
        if obj_id in seen:
            return f"<Circular Reference {hex(obj_id)}>"

        # pls stop killing my cpu
        if depth > self.max_depth:
            return str(type(obj).__name__) + "(...)"

        try:
            # Primitives
            if obj is None:
                return "None"
            if isinstance(obj, (bool, int, float, str)):
                return obj

            # fallback
            return str(obj)

        except Exception as e:
            return f"<Serialization Error: {str(e)}>"
        finally:
            if obj_id in seen:
                seen.remove(obj_id)
