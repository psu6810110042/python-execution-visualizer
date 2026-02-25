import types


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

            # MOST IMPORTANT DO NOT REMOVE
            if isinstance(obj, (list, tuple, dict, set)) or hasattr(obj, "__dict__"):
                seen.add(obj_id)

            # Lists / Tuples
            if isinstance(obj, (list, tuple)):
                if len(obj) > self.max_length:
                    return [
                        self._serialize_recursive(x, depth + 1, seen)
                        for x in obj[: self.max_length]
                    ] + [f"<truncated, total {len(obj)}>"]
                return [self._serialize_recursive(x, depth + 1, seen) for x in obj]

            # Sets
            if isinstance(obj, set):
                items = list(obj)
                if len(items) > self.max_length:
                    return {
                        "__type": "set",
                        "items": [
                            self._serialize_recursive(x, depth + 1, seen)
                            for x in items[: self.max_length]
                        ]
                        + [f"<truncated, total {len(items)}>"],
                    }
                return {
                    "__type": "set",
                    "items": [
                        self._serialize_recursive(x, depth + 1, seen) for x in items
                    ],
                }

            # Dicts
            if isinstance(obj, dict):
                result = {}
                keys = list(obj.keys())
                if len(keys) > self.max_length:
                    # serialize first N
                    for k in keys[: self.max_length]:
                        k_str = str(k)
                        result[k_str] = self._serialize_recursive(
                            obj[k], depth + 1, seen
                        )
                    result["__truncated"] = f"total {len(keys)}"
                else:
                    for k, v in obj.items():
                        k_str = str(k)
                        result[k_str] = self._serialize_recursive(v, depth + 1, seen)
                return result

            # Functions / Modules
            if isinstance(
                obj, (types.FunctionType, types.MethodType, types.ModuleType)
            ):
                return f"<{type(obj).__name__} {obj.__name__}>"

            # Generators / Iterators
            if isinstance(obj, types.GeneratorType):
                return f"<generator {obj.__name__}>"

            # Bytes / Bytearray
            if isinstance(obj, bytes):
                if len(obj) > 50:
                    return f"b'{obj[:50].hex()}...' ({len(obj)} bytes)"
                return f"b'{obj.hex()}'"

            if isinstance(obj, bytearray):
                if len(obj) > 50:
                    return f"bytearray({len(obj)} bytes)"
                return f"bytearray({list(obj)})"

            # Range objects
            if isinstance(obj, range):
                return f"range({obj.start}, {obj.stop}, {obj.step})"

            # Custom Objects
            if hasattr(obj, "__dict__"):

                return {
                    "__type": type(obj).__name__,
                    "__id": hex(obj_id),
                    "repr": str(obj),
                    "attributes": self._serialize_recursive(
                        obj.__dict__, depth + 1, seen
                    ),
                }

            # fallback
            return str(obj)

        except Exception as e:
            return f"<Serialization Error: {str(e)}>"
        finally:
            if obj_id in seen:
                seen.remove(obj_id)
