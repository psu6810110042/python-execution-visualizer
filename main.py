import threading

from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.utils import escape_markup, get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout

from core.executor import Executor
from core.terminal import InteractiveTerminal

Builder.load_file("interface.kv")

Window.minimum_width = 400
Window.minimum_height = 400


class RootLayout(MDBoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trace_data = []
        self.current_step = 0
        self.is_playing = False
        self._original_code = ""
        self.play_event = None
        self.watch_expressions = []

        Window.bind(on_keyboard=self._on_keyboard)

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        if key == 13 and "ctrl" in modifiers:
            self.start_visualization(self.ids.btn_run)
            return True

        if not self.ids.code_input.readonly:
            return False

        if key == 32:
            if self.trace_data:
                self.toggle_play(self.ids.btn_play)
            return True

        elif key == 275:
            self.step_visualization(1)
            return True

        elif key == 276:
            self.step_visualization(-1)
            return True

        elif key == 273:
            slider = self.ids.speed_slider
            slider.value = min(slider.max, round(slider.value + 0.1, 1))
            return True

        elif key == 274:
            slider = self.ids.speed_slider
            slider.value = max(slider.min, round(slider.value - 0.1, 1))
            return True

        return False

    def on_kv_post(self, base_widget):
        default_code = '# Write Python here\ndef foo():\n    print("test")\nfoo()'

        self.ids.code_input.text = default_code
        self.ids.code_input.bind(text=self._update_line_numbers)
        self.ids.code_input.bind(scroll_y=self._sync_scroll)
        self._update_line_numbers(self.ids.code_input, self.ids.code_input.text)
        
        # Start the backend shell process
        self.ids.terminal_display.start_shell()

    def _sync_scroll(self, instance, value):
        self.ids.line_numbers.scroll_y = value
        self.ids.line_numbers._update_graphics()

    def _update_line_numbers(self, instance, text, target=None):
        lines = text.count("\n") + 1
        nums = "\n".join([f"{i:3}" for i in range(1, lines + 1)])

        if target:
            target.text = nums
        else:
            self.ids.line_numbers.text = nums

    def start_visualization(self, instance):
        btn_text = self.ids.btn_run_text.text

        if btn_text == "Stop Edit":
            self.ids.code_input.readonly = False
            self.ids.editor_wrapper.opacity = 1
            self.ids.editor_wrapper.size_hint_y = 1

            self.ids.trace_wrapper.opacity = 0
            self.ids.trace_wrapper.size_hint_y = None
            self.ids.trace_wrapper.height = 0

            self.ids.code_input.text = getattr(self, "_original_code", "")

            self.ids.btn_run_text.text = "Run"
            self.ids.btn_run_icon.icon = "rocket-launch"
            instance.md_bg_color = get_color_from_hex("#0e639c")

            self.ids.terminal_display.clear()
            self.ids.terminal_display.start_shell()
            
            self.ids.variable_display.text = ""
            self.ids.memory_display.text = ""

            if self.is_playing:
                self.toggle_play(None)

            self.trace_data = []
            self.ids.step_scrubber.max = 1
            self.ids.step_scrubber.value = 0
            self.ids.step_scrubber.disabled = True
            self.ids.step_label.text = "0 / 0"
            self.ids.error_banner.height = "0dp"
            self.ids.error_banner.text = ""
            return

        code = self.ids.code_input.text
        if not code.strip():
            return

        if self.is_playing:
            self.toggle_play(None)

        self._original_code = code
        self.ids.code_input.readonly = True
        self.ids.code_input.focus = False

        self.ids.editor_wrapper.opacity = 0
        self.ids.editor_wrapper.size_hint_y = None
        self.ids.editor_wrapper.height = 0

        self.ids.trace_wrapper.opacity = 1
        self.ids.trace_wrapper.size_hint_y = 1

        self._update_line_numbers(None, code, target=self.ids.trace_line_numbers)

        self.ids.terminal_display.stop_shell()
        self.ids.terminal_display.clear()
        self.ids.terminal_display.output_text = "Executing...\n"
        self.ids.variable_display.text = ""
        self.ids.memory_display.text = ""

        self.ids.btn_run_text.text = "Stop Edit"
        self.ids.btn_run_icon.icon = "stop-circle"
        instance.md_bg_color = get_color_from_hex("#da3633")

        threading.Thread(target=self._run_in_thread, args=(code,), daemon=True).start()

    def _run_in_thread(self, code):
        try:
            executor = Executor(code=code, timeout=60.0) # increased timeout for manual inputs
            # Register executor with terminal so we can type stuff in matching input()
            self.ids.terminal_display.register_executor(executor)
            result = executor.execute()
            self._on_execution_finished(result)
        except Exception as e:
            self._on_execution_error(str(e))
        finally:
            self.ids.terminal_display.unregister_executor()

    @mainthread
    def _on_execution_finished(self, result):
        self.trace_data = result.get("steps", [])

        if not self.trace_data:
            err = result.get("error", "Trace failed or no steps captured.")
            self.ids.terminal_display.output_text += f"\n{err}"
            return

        max_step = max(1, len(self.trace_data) - 1)

        self.ids.step_scrubber.max = max_step
        self.ids.step_scrubber.value = 0
        self.ids.step_scrubber.disabled = False

        self.render_step(0)

        if not self.is_playing:
            self.toggle_play(None)

    @mainthread
    def _on_execution_error(self, err_msg):
        self.ids.terminal_display.output_text = f"Execution Error: {err_msg}"

    def render_step(self, step_idx):
        if not self.trace_data:
            return

        self.current_step = int(step_idx)
        state = self.trace_data[self.current_step]

        self.ids.step_label.text = f"{self.current_step} / {len(self.trace_data) - 1}"
        if int(self.ids.step_scrubber.value) != self.current_step:
            self.ids.step_scrubber.value = self.current_step

        self._render_code_trace(state)

        vars_text = self._format_variables(state.locals, "LOCALS")
        vars_text += self._format_variables(state.globals, "GLOBALS")

        self.ids.variable_display.markup = True
        self.ids.variable_display.text = (
            vars_text if vars_text else "[i][color=#555555]empty[/color][/i]"
        )

        self._render_call_stack(state)
        self._render_watch_expressions(state)

        self.ids.terminal_display.output_text = state.stdout

        if state.event == "exception" and state.exception:
            self.ids.error_banner.height = "40dp"
            self.ids.error_banner.text = (
                f"  [b]{state.exception['type']}[/b]: {state.exception['message']}"
            )
        else:
            self.ids.error_banner.height = "0dp"
            self.ids.error_banner.text = ""

    def _render_code_trace(self, state):
        code_lines = self._original_code.split("\n")
        rendered_code = ""
        trace_nums = []

        for i, raw_line in enumerate(code_lines):
            line_no = i + 1
            safe_line = escape_markup(raw_line)

            if line_no == state.line_number:
                color = "#ff5555" if state.event == "exception" else "#a6e22e"
                trace_nums.append(f"[color={color}]►[/color] {line_no}")
                rendered_code += f"[b][color={color}]{safe_line}[/color][/b]\n"
            else:
                trace_nums.append(f"{line_no}")
                rendered_code += f"{safe_line}\n"

        self.ids.code_display.text = rendered_code.rstrip("\n")
        self.ids.trace_line_numbers.text = "\n".join(trace_nums)

        label_height = max(
            self.ids.code_display.texture_size[1],
            self.ids.trace_line_numbers.texture_size[1],
        )
        scroll_height = self.ids.trace_wrapper.height
        total_lines = len(code_lines)

        if total_lines > 1 and label_height > scroll_height > 0:
            target_scroll = 1.0 - (state.line_number / total_lines)
            self.ids.trace_wrapper.scroll_y = max(0.0, min(1.0, target_scroll))

    def _format_variables(self, var_dict, title):
        if not var_dict:
            return ""

        text = f"[b][color=#858585]--- {title} ---[/color][/b]\n"
        for k, v in var_dict.items():
            if k == "input" or "mock_input" in str(v):
                continue

            if isinstance(v, dict) and "__type" in v:
                val_str = escape_markup(str(v.get("repr", "<object>")))
                type_str = v.get("__type")
            else:
                val_str = escape_markup(str(v))
                type_str = type(v).__name__

            text += f"[color=#9cdcfe]{k}[/color]  [color=#ce9178]{val_str}[/color]  [color=#4ec9b0][size=11sp]{type_str}[/size][/color]\n"
        return text + "\n"

    def _render_call_stack(self, state):
        stack_text = ""
        for i, func in enumerate(reversed(state.stack)):
            func_name = (
                func["name"] if isinstance(func, dict) and "name" in func else str(func)
            )

            if i == 0:
                stack_text += f"[color=#ffffff]> {func_name}[/color]\n"
            else:
                stack_text += f"[color=#aaaaaa]  {func_name}[/color]\n"

        self.ids.memory_display.markup = True
        self.ids.memory_display.text = (
            stack_text if stack_text else "[i][color=#555555]empty[/color][/i]"
        )

    def add_watch_expression(self):
        expr = self.ids.watch_input.text.strip()
        if expr and expr not in self.watch_expressions:
            self.watch_expressions.append(expr)
            self.ids.watch_input.text = ""
            if self.trace_data:
                self.render_step(self.current_step)
        else:
            self.ids.watch_input.text = ""
            
    def clear_watch_expressions(self):
        self.watch_expressions.clear()
        self.ids.watch_display.text = ""
        if self.trace_data:
            self.render_step(self.current_step)

    def _render_watch_expressions(self, state):
        if not self.watch_expressions:
            self.ids.watch_display.text = "[i][color=#555555]No expressions[/color][/i]"
            return

        watch_text = ""
        eval_globals = state.globals.copy()
        eval_locals = state.locals.copy()

        for expr in self.watch_expressions:
            try:
                # Basic eval using serialized subset 
                res = eval(expr, eval_globals, eval_locals)
                
                if isinstance(res, dict) and "__type" in res:
                    val_str = escape_markup(str(res.get("repr", "<object>")))
                    desc_type = res.get("__type")
                else:
                    val_str = escape_markup(str(res))
                    desc_type = type(res).__name__
                    
                color = "#ce9178"
                if isinstance(res, (int, float)):
                    color = "#b5cea8"
                elif isinstance(res, bool) or res is None:
                    color = "#569cd6"
                    
                watch_text += f"[color=#9cdcfe]{escape_markup(expr)}[/color]  [color={color}]{val_str}[/color]  [color=#4ec9b0][size=11sp]{desc_type}[/size][/color]\n"
            except Exception as e:
                watch_text += f"[color=#9cdcfe]{escape_markup(expr)}[/color]  [color=#f44747]Error: {type(e).__name__}[/color]\n"
                
        self.ids.watch_display.markup = True
        self.ids.watch_display.text = watch_text

    def update_speed(self, value):
        if self.is_playing and self.play_event:
            self.play_event.cancel()
            self.play_event = Clock.schedule_interval(self._play_tick, 0.5 / value)

    def toggle_play(self, instance):
        if not self.is_playing and self.current_step >= len(self.trace_data) - 1:
            self.render_step(0)

        self.is_playing = not self.is_playing
        btn = self.ids.btn_play

        if self.is_playing:
            btn.icon = "pause"
            btn.md_bg_color = get_color_from_hex("#da3633")  # VS Code red

            speed_val = self.ids.speed_slider.value
            self.play_event = Clock.schedule_interval(self._play_tick, 0.5 / speed_val)
        else:
            btn.icon = "play"
            btn.md_bg_color = get_color_from_hex("#0e639c")  # VS Code Blue

            if self.play_event:
                self.play_event.cancel()
                self.play_event = None

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


class PythonVisualizer(MDApp):
    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "LightBlue"
        self.theme_cls.accent_palette = "Amber"
        return RootLayout()


if __name__ == "__main__":
    PythonVisualizer().run()
