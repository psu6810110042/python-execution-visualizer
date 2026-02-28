from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.utils import get_color_from_hex


class DataGraph(StencilView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.frame_data = {}
        self.heap_data = {}

        # Colors
        self.c_bg = get_color_from_hex("#1e1e1e")
        self.c_frame_bg = get_color_from_hex("#252526")
        self.c_frame_border = get_color_from_hex("#3e3e42")
        self.c_heap_bg = get_color_from_hex("#2d2d30")
        self.c_text = get_color_from_hex("#d4d4d4")
        self.c_type = get_color_from_hex("#569cd6")
        self.c_string = get_color_from_hex("#ce9178")
        self.c_number = get_color_from_hex("#b5cea8")
        self.c_pointer = get_color_from_hex("#58a6ff")

    def build_graph(self, local_vars, global_vars):
        """Called every step to update the visualization data."""
        self.frame_data = {"Globals": global_vars, "Locals": local_vars}
        self.heap_data = {}
        
        # Extract heap objects (anything with __ref__)
        self._extract_heap(local_vars)
        self._extract_heap(global_vars)
        self.update_canvas()

    def _extract_heap(self, vars_dict):
        for k, v in vars_dict.items():
            self._traverse_for_heap(v)

    def _traverse_for_heap(self, obj):
        if isinstance(obj, dict) and "__ref__" in obj:
            ref_id = obj["__ref__"]
            if ref_id not in self.heap_data:
                # Store it in our heap registry
                self.heap_data[ref_id] = obj
                
                # Recursively extract from nested containers
                if obj["__type__"] == "list" or obj["__type__"] == "set":
                    for item in obj["value"]:
                        if item != "<truncated>":
                            self._traverse_for_heap(item)
                elif obj["__type__"] == "dict":
                    if isinstance(obj["value"], dict):
                        for k, v in obj["value"].items():
                            if k != "__truncated__":
                                self._traverse_for_heap(v)

    def update_canvas(self, *args):
        self.canvas.clear()
        
        if not self.frame_data and not self.heap_data:
            return

        with self.canvas:
            # Background
            Color(*self.c_bg)
            Rectangle(pos=self.pos, size=self.size)

        metrics = self._calculate_layout()
        self._draw_graph(metrics)

    def _calculate_layout(self):
        # A very basic layout algorithm
        metrics = {
            "frames": {},
            "heap": {},
            "pointers": []
        }
        
        # Constants
        PADDING = 20
        FRAME_W = 180
        ROW_H = 30
        
        # 1. Layout Frames (Left side)
        cur_y = self.top - PADDING
        for frame_name, frame_vars in self.frame_data.items():
            if not frame_vars:
                continue
                
            frame_h = ROW_H + (len(frame_vars) * ROW_H)
            metrics["frames"][frame_name] = {
                "x": self.x + PADDING,
                "y": cur_y - frame_h,
                "w": FRAME_W,
                "h": frame_h,
                "vars": frame_vars
            }
            cur_y -= frame_h + PADDING

        # 2. Layout Heap Objects (Right side)
        HEAP_START_X = self.x + PADDING + FRAME_W + 50
        HEAP_MIN_W = 120
        cur_y = self.top - PADDING
        
        for ref_id, obj in self.heap_data.items():
            obj_type = obj.get("__type__", "object")
            val = obj.get("value")
            
            # Calculate height based on type
            h = ROW_H * 2 # Header + at least one row
            w = HEAP_MIN_W
            
            if obj_type in ("list", "tuple", "set"):
                if isinstance(val, list):
                    h = ROW_H + (len(val) * ROW_H)
            elif obj_type == "dict":
                if isinstance(val, dict):
                    # +1 for header
                    keys = [k for k in val.keys() if k != "__truncated__"]
                    h = ROW_H + (len(keys) * ROW_H)
            
            metrics["heap"][ref_id] = {
                "x": HEAP_START_X,
                "y": cur_y - h,
                "w": w,
                "h": h,
                "obj": obj
            }
            cur_y -= h + PADDING
            
        return metrics

    def _draw_graph(self, metrics):
        with self.canvas:
            # 1. Draw Frames
            for frame_name, frame_metrics in metrics["frames"].items():
                self._draw_frame(frame_name, frame_metrics, metrics)
                
            # 2. Draw Heap Objects
            for ref_id, heap_metrics in metrics["heap"].items():
                self._draw_heap_object(ref_id, heap_metrics, metrics)
                
            # 3. Draw Pointers (Lines)
            self._draw_pointers(metrics)

    def _draw_frame(self, name, m, all_metrics):
        # Frame Box
        Color(*self.c_frame_bg)
        Rectangle(pos=(m["x"], m["y"]), size=(m["w"], m["h"]))
        Color(*self.c_frame_border)
        Line(rectangle=(m["x"], m["y"], m["w"], m["h"]), width=1)
        
        # Frame Title
        self._draw_text(name, m["x"] + 5, m["y"] + m["h"] - 25, self.c_text, bold=True)
        
        # Variables
        var_y = m["y"] + m["h"] - 55
        for var_name, var_val in m["vars"].items():
            # Var Name
            self._draw_text(var_name, m["x"] + 10, var_y, self.c_text)
            
            # Pointer Connection Point calculation
            val_x = m["x"] + m["w"] - 60
            
            if isinstance(var_val, dict) and "__ref__" in var_val:
                # It's a pointer to the heap
                ref_id = var_val["__ref__"]
                self._draw_text("   \u25CF", val_x, var_y, self.c_pointer) # Dot
                
                # Add pointer request
                if ref_id in all_metrics["heap"]:
                    all_metrics["pointers"].append({
                        "start": (m["x"] + m["w"] - 10, var_y + 10),
                        "end_ref": ref_id
                    })
            else:
                # It's a primitive value
                val_str = str(var_val)
                c = self.c_string if isinstance(var_val, str) else self.c_number
                self._draw_text(val_str[:15], val_x, var_y, c)
                
            var_y -= 30

    def _draw_heap_object(self, ref_id, m, all_metrics):
        obj = m["obj"]
        obj_type = obj.get("__type__", "object")
        val = obj.get("value")
        
        # Base Box
        Color(*self.c_heap_bg)
        Rectangle(pos=(m["x"], m["y"]), size=(m["w"], m["h"]))
        Color(*self.c_frame_border)
        Line(rectangle=(m["x"], m["y"], m["w"], m["h"]), width=1)
        
        # Header (Type)
        Color(0.2, 0.4, 0.6, 1) # Blueish header
        Rectangle(pos=(m["x"], m["y"] + m["h"] - 30), size=(m["w"], 30))
        self._draw_text(f"{obj_type}", m["x"] + 5, m["y"] + m["h"] - 25, (1,1,1,1), bold=True)
        
        # Content Slots
        content_y = m["y"] + m["h"] - 60
        ROW_H = 30
        
        if obj_type in ("list", "tuple", "set") and isinstance(val, list):
            # Draw Horizontal slots
            slot_w = min(40, max(20, m["w"] / max(1, len(val))))
            
            for i, item in enumerate(val):
                slot_x = m["x"] + (i * slot_w)
                
                # Draw separating lines
                if i > 0:
                    Color(*self.c_frame_border)
                    Line(points=[slot_x, content_y - ROW_H + 30, slot_x, content_y + 30], width=1)
                
                if item == "<truncated>":
                    self._draw_text("...", slot_x + 5, content_y, self.c_text)
                elif isinstance(item, dict) and "__ref__" in item:
                    # Pointer from array slot
                    self._draw_text("\u25CF", slot_x + slot_w/2 - 5, content_y, self.c_pointer)
                    if item["__ref__"] in all_metrics["heap"]:
                        all_metrics["pointers"].append({
                            "start": (slot_x + slot_w/2, content_y + 10),
                            "end_ref": item["__ref__"]
                        })
                else:
                    self._draw_text(str(item)[:5], slot_x + 2, content_y, self.c_number)
                
        elif obj_type == "dict" and isinstance(val, dict):
            # Key Value rows
            for k, v in val.items():
                if k == "__truncated__":
                    continue
                    
                # Dict key box
                Color(0.15, 0.15, 0.15, 1)
                Rectangle(pos=(m["x"], content_y), size=(40, ROW_H))
                self._draw_text(str(k)[:5], m["x"] + 5, content_y + 5, self.c_string)
                
                # Dict value
                if isinstance(v, dict) and "__ref__" in v:
                    self._draw_text("\u25CF", m["x"] + 60, content_y + 5, self.c_pointer)
                    if v["__ref__"] in all_metrics["heap"]:
                        all_metrics["pointers"].append({
                            "start": (m["x"] + 70, content_y + 15),
                            "end_ref": v["__ref__"]
                        })
                else:
                    self._draw_text(str(v)[:10], m["x"] + 50, content_y + 5, self.c_number)
                
                # Row separator
                Color(*self.c_frame_border)
                Line(points=[m["x"], content_y, m["x"] + m["w"], content_y], width=1)
                
                content_y -= ROW_H
        else:
            # Render simple value representation
            self._draw_text(str(val)[:15], m["x"] + 10, content_y, self.c_number)

    def _draw_pointers(self, metrics):
        Color(*self.c_pointer)
        for p in metrics["pointers"]:
            start_x, start_y = p["start"]
            target = metrics["heap"].get(p["end_ref"])
            
            if target:
                # Target top left
                end_x = target["x"]
                end_y = target["y"] + target["h"] - 15
                
                # Draw bezier curve connecting the two points
                # Control points for a smooth curve flowing left to right
                cp1_x = start_x + 30
                cp1_y = start_y
                cp2_x = end_x - 30
                cp2_y = end_y
                
                # Draw Line
                Line(bezier=(start_x, start_y, cp1_x, cp1_y, cp2_x, cp2_y, end_x, end_y), width=1.5)
                
                # Draw Arrowhead
                Line(points=[end_x - 5, end_y - 5, end_x, end_y, end_x - 5, end_y + 5], width=1.5)

    def _draw_text(self, text, x, y, color, bold=False):
        label = CoreLabel(text=str(text), font_name="RobotoMono-Regular", font_size=12, bold=bold)
        label.refresh()
        Color(*color)
        Rectangle(pos=(x, y), size=label.texture.size, texture=label.texture)
