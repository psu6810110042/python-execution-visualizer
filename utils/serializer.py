import types
import sys


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

        # memory bomb check (1MB limit)
        if sys.getsizeof(obj, 0) > 1024 * 1024:
            return "<Data too large to visualize>"

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
                items = []
                if len(obj) > self.max_length:
                    items = [self._serialize_recursive(x, depth + 1, seen) for x in obj[: self.max_length]]
                    items.append("<truncated>")
                else:
                    items = [self._serialize_recursive(x, depth + 1, seen) for x in obj]
                    
                return {
                    "__ref__": hex(obj_id),
                    "__type__": type(obj).__name__,
                    "value": items
                }

            # Sets
            if isinstance(obj, set):
                items = list(obj)
                val_items = []
                if len(items) > self.max_length:
                    val_items = [self._serialize_recursive(x, depth + 1, seen) for x in items[: self.max_length]]
                    val_items.append("<truncated>")
                else:
                    val_items = [self._serialize_recursive(x, depth + 1, seen) for x in items]
                    
                return {
                    "__ref__": hex(obj_id),
                    "__type__": "set",
                    "value": val_items
                }

            # Dicts
            if isinstance(obj, dict):
                result = {}
                keys = list(obj.keys())
                if len(keys) > self.max_length:
                    for k in keys[: self.max_length]:
                        result[str(k)] = self._serialize_recursive(obj[k], depth + 1, seen)
                    result["__truncated"] = f"total {len(keys)}"
                else:
                    for k, v in obj.items():
                        result[str(k)] = self._serialize_recursive(v, depth + 1, seen)
                        
                return {
                    "__ref__": hex(obj_id),
                    "__type__": "dict",
                    "value": result
                }

            # Functions / Modules
            if isinstance(
                obj, (types.FunctionType, types.MethodType, types.ModuleType)
            ):
                return {
                    "__ref__": hex(obj_id),
                    "__type__": type(obj).__name__,
                    "value": f"{obj.__name__}"
                }

            # Generators / Iterators
            if isinstance(obj, types.GeneratorType):
                return {
                    "__ref__": hex(obj_id),
                    "__type__": "generator",
                    "value": f"{obj.__name__}"
                }

            # Bytes / Bytearray
            if isinstance(obj, bytes):
                val = f"b'{obj[:50].hex()}...' ({len(obj)} bytes)" if len(obj) > 50 else f"b'{obj.hex()}'"
                return {
                    "__ref__": hex(obj_id),
                    "__type__": type(obj).__name__,
                    "value": val
                }

            if isinstance(obj, bytearray):
                val = f"bytearray({len(obj)} bytes)" if len(obj) > 50 else f"bytearray({list(obj)})"
                return {
                    "__ref__": hex(obj_id),
                    "__type__": type(obj).__name__,
                    "value": val
                }

            # Range objects
            if isinstance(obj, range):
                return {
                    "__ref__": hex(obj_id),
                    "__type__": "range",
                    "value": f"range({obj.start}, {obj.stop}, {obj.step})"
                }

            # Custom Objects
            if hasattr(obj, "__dict__"):
                return {
                    "__ref__": hex(obj_id),
                    "__type__": type(obj).__name__,
                    "value": self._serialize_recursive(obj.__dict__, depth + 1, seen)
                }

            # fallback
            return str(obj)

        except Exception as e:
            return f"<Serialization Error: {str(e)}>"
        finally:
            if obj_id in seen:
                seen.remove(obj_id)
