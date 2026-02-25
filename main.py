import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.lang import Builder
from kivy.clock import Clock
import kivy.utils as utils
from kivy.utils import escape_markup

from core.executor import Executor

Builder.load_file("interface.kv")


class RootLayout(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trace_data = []
        self.current_step = 0
        self.is_playing = False

        Clock.schedule_once(self._init_editor, 0)

    def _init_editor(self, dt):
        self._safe_ids = {k: v for k, v in self.ids.items()}
        self._safe_ids["code_input"].text = (
            '# Write Python here\ndef foo():\n    print("test")\nfoo()'
        )
        self._safe_ids["code_input"].bind(text=self._update_line_numbers)
        self._safe_ids["code_input"].bind(scroll_y=self._sync_scroll)
        self._update_line_numbers(
            self._safe_ids["code_input"], self._safe_ids["code_input"].text
        )

    def _sync_scroll(self, instance, value):
        self._safe_ids["line_numbers"].scroll_y = value
        self._safe_ids["line_numbers"]._update_graphics()

    def _update_line_numbers(self, instance, text, target=None):
        lines = text.count("\n") + 1
        nums = "\n".join([f"{i:3}" for i in range(1, lines + 1)])
        if target:
            target.text = nums
        else:
            self._safe_ids["line_numbers"].text = nums

    def start_visualization(self, instance):
        """Parse code and generate the trace."""
        if instance.text == "Stop Edit":
            self._safe_ids["code_input"].readonly = False
            self._safe_ids["editor_wrapper"].opacity = 1
            self._safe_ids["editor_wrapper"].size_hint_y = 1

            self._safe_ids["trace_wrapper"].opacity = 0
            self._safe_ids["trace_wrapper"].size_hint_y = None
            self._safe_ids["trace_wrapper"].height = 0

            self._safe_ids["code_input"].text = getattr(self, "_original_code", "")

            instance.text = "Run ->"
            instance.background_color = utils.get_color_from_hex("#0e639c")
            self._safe_ids["output_display"].text = ""
            self._safe_ids["variable_display"].text = ""
            self._safe_ids["memory_display"].text = ""

            if self.is_playing:
                self.toggle_play(None)

            self.trace_data = []
            self._safe_ids["step_scrubber"].max = 0
            self._safe_ids["step_scrubber"].value = 0
            self._safe_ids["step_label"].text = "0 / 0"
            self._safe_ids["error_banner"].height = "0dp"
            self._safe_ids["error_banner"].text = ""
            return

        code = self._safe_ids["code_input"].text
        if not code.strip():
            return

        if self.is_playing:
            self.toggle_play(None)

        self._safe_ids["code_input"].readonly = True
        self._original_code = code
        self._safe_ids["editor_wrapper"].opacity = 0
        self._safe_ids["editor_wrapper"].size_hint_y = None
        self._safe_ids["editor_wrapper"].height = 0

        self._safe_ids["trace_wrapper"].opacity = 1
        self._safe_ids["trace_wrapper"].size_hint_y = 1

        self._update_line_numbers(
            None, code, target=self._safe_ids["trace_line_numbers"]
        )

        self._safe_ids["output_display"].text = "Executing..."
        self._safe_ids["variable_display"].text = ""
        self._safe_ids["memory_display"].text = ""

        instance.text = "Stop Edit"
        instance.background_color = utils.get_color_from_hex("#da3633")

        import threading
        from kivy.clock import mainthread

        try:

            def _run_in_thread():
                try:
                    executor = Executor(code=code, timeout=5.0)
                    result = executor.execute()
                    self._on_execution_finished(result)
                except Exception as e:
                    self._on_execution_error(str(e))

            threading.Thread(target=_run_in_thread, daemon=True).start()

        except Exception as e:
            self._safe_ids["output_display"].text = f"Execution Error: {str(e)}"

    from kivy.clock import mainthread

    @mainthread
    def _on_execution_finished(self, result):
        self.trace_data = result["steps"]
        if not self.trace_data:
            err = result.get("error")
            self._safe_ids["output_display"].text = (
                err if err else "Trace failed or no steps captured."
            )
            return

        max_step = len(self.trace_data) - 1
        self._safe_ids["step_scrubber"].max = max_step
        self._safe_ids["step_scrubber"].value = 0

        self.render_step(0)

    @mainthread
    def _on_execution_error(self, err_msg):
        self._safe_ids["output_display"].text = f"Execution Error: {err_msg}"

    def render_step(self, step_idx):
        """Update all displays based on the trace state."""
        if not self.trace_data:
            return

        self.current_step = int(step_idx)
        step_idx = int(step_idx)
        state = self.trace_data[step_idx]

        # print(f"render_step called. trace_data size: {len(self.trace_data)}. active ids: {self.ids.keys()}")
        self._safe_ids["step_label"].text = f"{step_idx} / {len(self.trace_data)-1}"

        if int(self._safe_ids["step_scrubber"].value) != step_idx:
            self._safe_ids["step_scrubber"].value = step_idx

        code_lines = self._original_code.split("\n")

        rendered_code = ""
        trace_nums = []
        for i, raw_line in enumerate(code_lines):
            line_no = i + 1
            safe_line = escape_markup(raw_line)

            if line_no == state.line_number:
                if state.event == "exception":
                    trace_nums.append(f"[color=#ff5555]►[/color] {line_no}")
                    rendered_code += f"[b][color=#ff5555]{safe_line}[/color][/b]\n"
                else:
                    trace_nums.append(f"[color=#a6e22e]►[/color] {line_no}")
                    rendered_code += f"[b][color=#a6e22e]{safe_line}[/color][/b]\n"
            else:
                trace_nums.append(f"{line_no}")
                rendered_code += f"{safe_line}\n"

        self._safe_ids["code_display"].text = rendered_code.rstrip("\n")
        self._safe_ids["trace_line_numbers"].text = "\n".join(trace_nums)

        label_height = max(
            self._safe_ids["code_display"].texture_size[1],
            self._safe_ids["trace_line_numbers"].texture_size[1],
        )
        scroll_height = self._safe_ids["trace_wrapper"].height

        total_lines = len(code_lines)
        if total_lines > 1 and label_height > scroll_height and scroll_height > 0:
            line_pct = state.line_number / total_lines
            target_scroll = 1.0 - line_pct

            target_scroll = max(0.0, min(1.0, target_scroll))
            self._safe_ids["trace_wrapper"].scroll_y = target_scroll

        vars_text = ""

        if state.locals:
            vars_text += "[b][color=#858585]--- LOCALS ---[/color][/b]\n"
            for k, v in state.locals.items():
                if k == "input" or "mock_input" in str(v):
                    continue
                if isinstance(v, dict) and "__type" in v:
                    vars_text += f"[color=#9cdcfe]{k}[/color]  [color=#ce9178]{v.get('repr', '<object>')}[/color]  [color=#4ec9b0][size=11sp]{v.get('__type')}[/size][/color]\n"
                else:
                    vars_text += f"[color=#9cdcfe]{k}[/color]  [color=#ce9178]{v}[/color]  [color=#4ec9b0][size=11sp]{type(v).__name__}[/size][/color]\n"
            vars_text += "\n"

        if state.globals:
            vars_text += "[b][color=#858585]--- GLOBALS ---[/color][/b]\n"
            for k, v in state.globals.items():
                if k == "input" or "mock_input" in str(v):
                    continue
                if isinstance(v, dict) and "__type" in v:
                    vars_text += f"[color=#9cdcfe]{k}[/color]  [color=#ce9178]{v.get('repr', '<object>')}[/color]  [color=#4ec9b0][size=11sp]{v.get('__type')}[/size][/color]\n"
                else:
                    vars_text += f"[color=#9cdcfe]{k}[/color]  [color=#ce9178]{v}[/color]  [color=#4ec9b0][size=11sp]{type(v).__name__}[/size][/color]\n"

        self._safe_ids["variable_display"].markup = True
        self._safe_ids["variable_display"].text = (
            vars_text if vars_text else "[i][color=#555555]empty[/color][/i]"
        )

        stack_text = ""
        for i, func in enumerate(reversed(state.stack)):
            func_name = str(func)
            if isinstance(func, dict) and "name" in func:
                func_name = func["name"]
            
            if i == 0:
                stack_text += f"[color=#ffffff]> {func_name}[/color]\n"
            else:
                stack_text += f"[color=#aaaaaa]  {func_name}[/color]\n"
        self._safe_ids["memory_display"].markup = True
        self._safe_ids["memory_display"].text = (
            stack_text if stack_text else "[i][color=#555555]empty[/color][/i]"
        )

        out_text = state.stdout
        self._safe_ids["output_display"].markup = True
        self._safe_ids["output_display"].text = out_text

        if state.event == "exception" and state.exception:
            self._safe_ids["error_banner"].height = "40dp"
            self._safe_ids["error_banner"].text = (
                f"  [b]{state.exception['type']}[/b]: {state.exception['message']}"
            )
        else:
            self._safe_ids["error_banner"].height = "0dp"
            self._safe_ids["error_banner"].text = ""

    def toggle_play(self, instance):
        self.is_playing = not self.is_playing

        btn = self._safe_ids["btn_play"]
        if self.is_playing:
            btn.text = "Pause"
            btn.background_color = utils.get_color_from_hex("#da3633")  # VS Code red

            speed_val = self._safe_ids["speed_slider"].value
            interval = 0.5 / speed_val
            self.play_event = Clock.schedule_interval(self._play_tick, interval)
        else:
            btn.text = "Play"
            btn.background_color = utils.get_color_from_hex("#0e639c")  # VS Code Blue

            if hasattr(self, "play_event"):
                self.play_event.cancel()

    def _play_tick(self, dt):
        if self.current_step < len(self.trace_data) - 1:
            self.render_step(self.current_step + 1)
        else:
            self.toggle_play(None)  # Auto pause at end

    def step_visualization(self, delta):
        if self.is_playing:
            self.toggle_play(None)

        new_step = self.current_step + delta
        if 0 <= new_step < len(self.trace_data):
            self.render_step(new_step)


class PythonVisualizer(App):
    def build(self):
        return RootLayout()


if __name__ == "__main__":
    PythonVisualizer().run()
