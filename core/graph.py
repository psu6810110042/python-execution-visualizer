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
        self.c_frame_border = get_color_from_hex("#444444")
        self.c_heap_bg = get_color_from_hex("#2d2d30")
        self.c_text = get_color_from_hex("#e0e0e0")
        self.c_type_list = get_color_from_hex("#dcdcaa") # Yellowish
        self.c_type_dict = get_color_from_hex("#c586c0") # Purplish
        self.c_type_other = get_color_from_hex("#569cd6") # Blueish
        self.c_string = get_color_from_hex("#ce9178")
        self.c_number = get_color_from_hex("#b5cea8")
        self.c_pointer = get_color_from_hex("#58a6ff")
        self.c_null = get_color_from_hex("#858585")

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

    def on_parent(self, widget, parent):
        if parent:
            parent.bind(size=self._on_parent_size)
            
    def _on_parent_size(self, instance, size):
        self.update_canvas()

    def update_canvas(self, *args):
        # Prevent recursive size updates
        if getattr(self, '_updating_canvas', False):
            return
            
        self._updating_canvas = True
        self.canvas.clear()
        
        if not self.frame_data and not self.heap_data:
            self._updating_canvas = False
            return

        # 1. Calculate required dimensions with a dummy base_y
        metrics = self._calculate_layout(base_y=0)
        
        max_w = 0
        min_y = 0
        
        for f in metrics["frames"].values():
            if f["x"] + f["w"] + 50 > max_w: max_w = f["x"] + f["w"] + 50
            if f["y"] < min_y: min_y = f["y"]
            
        for h in metrics["heap"].values():
            if h["x"] + h["w"] + 50 > max_w: max_w = h["x"] + h["w"] + 50
            if h["y"] < min_y: min_y = h["y"]
            
        required_h = -min_y + 100
        
        parent_w = self.parent.width if self.parent else 600
        parent_h = self.parent.height if self.parent else 600
        
        target_w = max(parent_w, max_w)
        target_h = max(parent_h, required_h)
        
        size_changed = False
        if abs(self.width - target_w) > 1 or abs(self.height - target_h) > 1:
            self.size = (target_w, target_h)
            size_changed = True

        if size_changed and args:
            # If we were called by a pos/size binding and just changed size again,
            # we should return and let Kivy trigger the next update_canvas
            self._updating_canvas = False
            return

        with self.canvas:
            # Background
            Color(*self.c_bg)
            Rectangle(pos=self.pos, size=self.size)

        # 2. Recalculate with actual bounds
        metrics = self._calculate_layout(base_y=self.top)
        self._draw_graph(metrics)
        self._updating_canvas = False

    def _calculate_layout(self, base_y):
        # A very basic layout algorithm
        metrics = {
            "frames": {},
            "heap": {},
            "pointers": []
        }
        
        # Constants
        PADDING = 80
        FRAME_W = 260
        ROW_H = 45
        
        # 1. Layout Frames (Left side)
        cur_y = base_y - PADDING
        for frame_name, frame_vars in self.frame_data.items():
            if not frame_vars:
                continue
                
            frame_h = ROW_H + (len(frame_vars) * ROW_H) + 10
            
            # Dynamic width calculation
            max_k_len = max([len(str(k)) for k in frame_vars.keys()] + [0])
            max_v_len = max([5 if (isinstance(v, dict) and "__ref__" in v) else len(str(v)) for v in frame_vars.values()] + [0])
            
            # Title width check
            title_w = len(frame_name) * 11 + 30
            
            req_w = 20 + max_k_len * 11 + 40 + max_v_len * 11 + 20
            max_w = max(FRAME_W, req_w, title_w)
            
            metrics["frames"][frame_name] = {
                "x": self.x + PADDING,
                "y": cur_y - frame_h,
                "w": max_w,
                "h": frame_h,
                "vars": frame_vars,
                "val_x_offset": 20 + max_k_len * 11 + 40
            }
            cur_y -= frame_h + PADDING

        # 2. Layout Heap Objects (Right side)
        HEAP_START_X = self.x + PADDING + FRAME_W + 200
        HEAP_MIN_W = 240
        cur_y = base_y - PADDING
        
        for ref_id, obj in self.heap_data.items():
            obj_type = obj.get("__type__", "object")
            val = obj.get("value")
            
            # Calculate height based on type
            h = ROW_H + 20 # Header
            w = HEAP_MIN_W
            
            val_x_offset = 0
            k_box_w = 0
            
            title_w = len(obj_type) * 11 + 100
            
            if obj_type in ("list", "tuple", "set"):
                if isinstance(val, list):
                    max_item_len = max([5 if (isinstance(x, dict) and "__ref__" in x) else (3 if x == "<truncated>" else len(str(x))) for x in val] + [0])
                    slot_w = max_item_len * 11 + 40
                    w = max(HEAP_MIN_W, title_w, len(val) * slot_w)
                    h += ROW_H
            elif obj_type == "dict":
                if isinstance(val, dict):
                    keys = [k for k in val.keys() if k != "__truncated__"]
                    h += max(1, len(keys)) * ROW_H
                    
                    max_k_len = max([len(str(k)) for k in keys] + [0])
                    max_v_len = max([5 if (isinstance(v, dict) and "__ref__" in v) else len(str(v)) for k, v in val.items() if k != "__truncated__"] + [0])
                    
                    k_box_w = max_k_len * 11 + 20
                    req_w = k_box_w + 30 + max_v_len * 11 + 20
                    w = max(HEAP_MIN_W, title_w, req_w)
                    val_x_offset = k_box_w + 30
            else:
                 h += ROW_H
                 w = max(HEAP_MIN_W, title_w, 20 + len(str(val)) * 11 + 20)
            
            metrics["heap"][ref_id] = {
                "x": HEAP_START_X,
                "y": cur_y - h,
                "w": w,
                "h": h,
                "obj": obj,
                "val_x_offset": val_x_offset,
                "k_box_w": k_box_w
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
        Line(rectangle=(m["x"], m["y"], m["w"], m["h"]), width=1.8)
        
        # Frame Title
        Color(*self.c_bg)
        Rectangle(pos=(m["x"], m["y"] + m["h"] - 45), size=(m["w"], 45))
        self._draw_text(name, m["x"] + 15, m["y"] + m["h"] - 32, self.c_text, bold=True, size=18)
        Color(*self.c_frame_border)
        Line(points=[m["x"], m["y"] + m["h"] - 45, m["x"] + m["w"], m["y"] + m["h"] - 45], width=1.8)
        
        # Variables
        var_y = m["y"] + m["h"] - 85
        for var_name, var_val in m["vars"].items():
            # Var Name
            self._draw_text(var_name, m["x"] + 20, var_y, self.c_text, size=18)
            
            # Pointer Connection Point calculation
            val_x = m["x"] + m.get("val_x_offset", m["w"] / 2)
            
            if isinstance(var_val, dict) and "__ref__" in var_val:
                ref_id = var_val["__ref__"]
                self._draw_text("   \u25CF", val_x, var_y - 2, self.c_pointer, size=24) 
                
                if ref_id in all_metrics["heap"]:
                    all_metrics["pointers"].append({
                        "start": (val_x + 50, var_y + 15),
                        "end_ref": ref_id
                    })
            else:
                val_str = str(var_val)
                c = self.c_string if isinstance(var_val, str) else self.c_number
                if val_str == "None": c = self.c_null
                self._draw_text(val_str, val_x, var_y, c, size=18)
                
            var_y -= 45

    def _draw_heap_object(self, ref_id, m, all_metrics):
        obj = m["obj"]
        obj_type = obj.get("__type__", "object")
        val = obj.get("value")
        
        # Base Box
        Color(*self.c_heap_bg)
        Rectangle(pos=(m["x"], m["y"]), size=(m["w"], m["h"]))
        Color(*self.c_frame_border)
        Line(rectangle=(m["x"], m["y"], m["w"], m["h"]), width=1.8)
        
        # Header Color based on Type
        header_color = self.c_type_other
        if obj_type in ("list", "tuple", "set"):
            header_color = self.c_type_list
        elif obj_type == "dict":
            header_color = self.c_type_dict
            
        Color(*header_color)
        header_h = 45
        Rectangle(pos=(m["x"], m["y"] + m["h"] - header_h), size=(m["w"], header_h))
        self._draw_text(f"{obj_type}", m["x"] + 12, m["y"] + m["h"] - 32, (0.1, 0.1, 0.1, 1), bold=True, size=18)
        
        # Draw ID ref in header
        id_str = str(ref_id)[-4:]  # Last 4 chars of hex
        self._draw_text(f"id:{id_str}", m["x"] + m["w"] - 75, m["y"] + m["h"] - 30, (0.2, 0.2, 0.2, 0.8), size=14)
        
        content_y = m["y"] + m["h"] - header_h - 38
        ROW_H = 45
        
        if obj_type in ("list", "tuple", "set") and isinstance(val, list):
            # Draw Horizontal slots
            slot_w = m["w"] / max(1, len(val))
            
            for i, item in enumerate(val):
                slot_x = m["x"] + (i * slot_w)
                
                # Draw separating lines
                if i > 0:
                    Color(*self.c_frame_border)
                    Line(points=[slot_x, content_y - 5, slot_x, content_y + ROW_H - 5], width=1.5)
                
                # Draw index small text below box
                self._draw_text(str(i), slot_x + slot_w/2 - 5, content_y - 25, self.c_null, size=14)
                
                if item == "<truncated>":
                    self._draw_text("...", slot_x + slot_w/2 - 12, content_y, self.c_text, size=18)
                elif isinstance(item, dict) and "__ref__" in item:
                    # Pointer from array slot
                    self._draw_text("\u25CF", slot_x + slot_w/2 - 8, content_y, self.c_pointer, size=24)
                    if item["__ref__"] in all_metrics["heap"]:
                        all_metrics["pointers"].append({
                            "start": (slot_x + slot_w/2 + 2, content_y + 15),
                            "end_ref": item["__ref__"]
                        })
                else:
                    v_str = str(item)
                    c = self.c_string if isinstance(item, str) else self.c_number
                    if v_str == "None": c = self.c_null
                    self._draw_text(v_str, slot_x + 15, content_y, c, size=18)
                
        elif obj_type == "dict" and isinstance(val, dict):
            # Key Value rows
            val_x = m["val_x_offset"]
            k_box_w = m["k_box_w"]
            
            for k, v in val.items():
                if k == "__truncated__":
                    continue
                    
                # Dict key box
                Color(0.15, 0.15, 0.15, 1)
                Rectangle(pos=(m["x"], content_y - 5), size=(k_box_w, ROW_H))
                self._draw_text(str(k), m["x"] + 12, content_y + 2, self.c_string, size=18)
                
                # Dict value
                if isinstance(v, dict) and "__ref__" in v:
                    self._draw_text("\u25CF", m["x"] + val_x + 10, content_y, self.c_pointer, size=24)
                    if v["__ref__"] in all_metrics["heap"]:
                        all_metrics["pointers"].append({
                            "start": (m["x"] + val_x + 20, content_y + 15),
                            "end_ref": v["__ref__"]
                        })
                else:
                    v_str = str(v)
                    c = self.c_string if isinstance(v, str) else self.c_number
                    if v_str == "None": c = self.c_null
                    self._draw_text(v_str, m["x"] + val_x, content_y + 2, c, size=18)
                
                # Row separator
                Color(*self.c_frame_border)
                Line(points=[m["x"], content_y - 5, m["x"] + m["w"], content_y - 5], width=1.5)
                
                content_y -= ROW_H
        else:
            # Render simple value representation
            self._draw_text(str(val), m["x"] + 20, content_y, self.c_number, size=18)

    def _draw_pointers(self, metrics):
        for p in metrics["pointers"]:
            start_x, start_y = p["start"]
            target = metrics["heap"].get(p["end_ref"])
            
            if target:
                end_x = target["x"]
                # Point to middle left edge of the target bounding box
                end_y = target["y"] + (target["h"] / 2)
                
                cp1_x = start_x + 120
                cp1_y = start_y
                cp2_x = end_x - 120
                cp2_y = end_y
                
                Color(*self.c_pointer)
                # Ensure the line pops more by drawing a dark background line slightly thicker first
                Color(0.1, 0.1, 0.1, 0.8)
                Line(bezier=(start_x, start_y, cp1_x, cp1_y, cp2_x, cp2_y, end_x, end_y), width=2.5)
                
                Color(*self.c_pointer)
                Line(bezier=(start_x, start_y, cp1_x, cp1_y, cp2_x, cp2_y, end_x, end_y), width=1.5)

    def _draw_text(self, text, x, y, color, bold=False, size=12):
        label = CoreLabel(text=str(text), font_name="RobotoMono-Regular", font_size=size, bold=bold)
        label.refresh()
        Color(*color)
        Rectangle(pos=(x, y), size=label.texture.size, texture=label.texture)
