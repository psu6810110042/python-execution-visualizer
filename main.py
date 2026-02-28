import threading

from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, Line
from kivy.lang import Builder
from kivy.utils import escape_markup, get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.menu import MDDropdownMenu

from core.examples import EXAMPLES
from core.executor import Executor
from core.terminal import InteractiveTerminal
from plyer import filechooser

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
        self._examples_menu = None
        self.current_file_path = None

        Window.bind(on_keyboard=self._on_keyboard)
        # Track panel visible states
        self._panel_visible = {"terminal": True, "right": True}

    def _on_keyboard(self, window, key, scancode, codepoint, modifiers):
        if key == 13 and "ctrl" in modifiers:
            self.start_visualization(self.ids.btn_run)
            return True

        # Ctrl+1 → toggle terminal panel
        if key == ord("1") and "ctrl" in modifiers:
            self.toggle_panel("terminal")
            return True

        # Ctrl+` (backtick, key 96) → toggle right panel
        if key == 96 and "ctrl" in modifiers:
            self.toggle_panel("right")
            return True

        # Ctrl+2 → toggle code editor panel
        if key == ord("2") and "ctrl" in modifiers:
            self.toggle_panel("editor")
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

        # Prepare canvas border instructions for focus highlight
        self._editor_focus_color = None
        self._editor_focus_line = None
        self._terminal_focus_color = None
        self._terminal_focus_line = None
        self._setup_focus_borders()

        # Start the backend shell process
        self.ids.terminal_display.start_shell()
        self.ids.terminal_display.on_focus_changed = self.set_terminal_focus

    def open_examples_menu(self, caller):
        """Build (once) and open the built-in examples dropdown menu."""
        if self._examples_menu is None:
            items = [
                {
                    "text": ex["title"],
                    "on_release": (lambda key=i: self.load_example(key)),
                }
                for i, ex in enumerate(EXAMPLES)
            ]
            self._examples_menu = MDDropdownMenu(
                caller=caller,
                items=items,
                width_mult=4,
            )
        else:
            self._examples_menu.caller = caller
        self._examples_menu.open()

    def load_example(self, index):
        """Load the selected example into the code editor."""
        self._examples_menu.dismiss()
        code = EXAMPLES[index]["code"]
        self.ids.code_input.readonly = False
        self.ids.code_input.text = code
        self.ids.code_input.focus = True
        self.current_file_path = None

    def show_load_dialog(self, _caller=None):
        """Open a native file load dialog."""
        filechooser.open_file(on_selection=self.load_file)

    def load_file(self, selection):
        if not selection:
            return
        path = selection[0]
        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()
            self.ids.code_input.readonly = False
            self.ids.code_input.text = code
            self.ids.code_input.focus = True
            self.current_file_path = path
        except Exception as e:
            self._on_execution_error(f"Failed to load file: {e}")

    def save_file(self, _caller=None):
        if self.current_file_path:
            try:
                with open(self.current_file_path, "w", encoding="utf-8") as f:
                    f.write(self.ids.code_input.text)
            except Exception as e:
                self._on_execution_error(f"Failed to save file: {e}")
        else:
            self.save_file_as()

    def save_file_as(self, _caller=None):
        """Open a native file save dialog."""
        filechooser.save_file(on_selection=self._on_save_file_as_selection)

    def _on_save_file_as_selection(self, selection):
        if not selection:
            return
        path = selection[0]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.ids.code_input.text)
            self.current_file_path = path
        except Exception as e:
            self._on_execution_error(f"Failed to save file: {e}")

    def _setup_focus_borders(self):
        """Pre-create canvas border instructions for editor and terminal panels."""
        UNFOCUSED = (0, 0, 0, 0)
        # Editor panel border
        panel = self.ids.editor_panel
        with panel.canvas.after:
            self._editor_focus_color = Color(*UNFOCUSED)
            self._editor_focus_line = Line(
                rectangle=(panel.x, panel.y, panel.width, panel.height),
                width=1.2,
            )
        panel.bind(
            pos=self._update_editor_border,
            size=self._update_editor_border,
        )
        # Terminal panel border
        term = self.ids.terminal_panel
        with term.canvas.after:
            self._terminal_focus_color = Color(*UNFOCUSED)
            self._terminal_focus_line = Line(
                rectangle=(term.x, term.y, term.width, term.height),
                width=1.2,
            )
        term.bind(
            pos=self._update_terminal_border,
            size=self._update_terminal_border,
        )

    def _update_editor_border(self, instance, _value):
        if self._editor_focus_line:
            self._editor_focus_line.rectangle = (
                instance.x, instance.y, instance.width, instance.height
            )

    def _update_terminal_border(self, instance, _value):
        if self._terminal_focus_line:
            self._terminal_focus_line.rectangle = (
                instance.x, instance.y, instance.width, instance.height
            )

    def set_editor_focus(self, focused):
        """Toggle the focus border on the Code Editor panel."""
        FOCUSED = (0.6, 0.6, 0.6, 0.4)
        UNFOCUSED = (0, 0, 0, 0)
        if self._editor_focus_color:
            self._editor_focus_color.rgba = FOCUSED if focused else UNFOCUSED
        if focused and self._terminal_focus_color:
            self._terminal_focus_color.rgba = UNFOCUSED

    def set_terminal_focus(self, focused):
        """Toggle the focus border on the Terminal panel."""
        FOCUSED = (0.6, 0.6, 0.6, 0.4)
        UNFOCUSED = (0, 0, 0, 0)
        if self._terminal_focus_color:
            self._terminal_focus_color.rgba = FOCUSED if focused else UNFOCUSED
        if focused and self._editor_focus_color:
            self._editor_focus_color.rgba = UNFOCUSED

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

            # Reset panel proportions to defaults regardless of toggle state
            self.ids.editor_splitter.size_hint_y = 0.7
            self.ids.editor_splitter.opacity = 1
            self.ids.terminal_panel.size_hint_y = 1
            self.ids.terminal_panel.opacity = 1
            self._panel_visible["terminal"] = True
            self._panel_visible["editor"] = True

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
            executor = Executor(
                code=code, timeout=60.0
            )  # increased timeout for manual inputs
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

    def toggle_panel(self, panel_name):
        """Show or hide a named panel by toggling size_hint and opacity."""
        visible = self._panel_visible.get(panel_name, True)
        new_visible = not visible
        self._panel_visible[panel_name] = new_visible

        if panel_name == "terminal":
            panel = self.ids.terminal_panel
            btn = self.ids.terminal_toggle_btn
            editor = self.ids.editor_splitter
            if new_visible:
                # Restore both: terminal fills remaining space, editor goes back to 70%
                panel.size_hint_y = 1
                panel.opacity = 1
                editor.size_hint_y = 0.7
                btn.icon = "chevron-down"
            else:
                # Hide terminal and let editor expand to full height
                panel.size_hint_y = None
                panel.height = 0
                panel.opacity = 0
                editor.size_hint_y = 1
                btn.icon = "chevron-up"

        elif panel_name == "right":
            panel = self.ids.right_panel
            splitter = self.ids.left_splitter
            if new_visible:
                panel.size_hint_x = 0.4  # restore right panel to 40% width
                panel.opacity = 1
                splitter.size_hint_x = 0.6
            else:
                panel.size_hint_x = None
                panel.width = 0
                panel.opacity = 0
                splitter.size_hint_x = 1

        elif panel_name == "editor":
            # The editor_splitter is a LoadSplitter — hiding it by collapsing size_hint_y
            editor = self.ids.editor_splitter
            terminal = self.ids.terminal_panel
            # new_visible was already computed at top of this method
            if new_visible:
                editor.size_hint_y = 0.7
                editor.opacity = 1
                # Restore terminal to share space if it's visible
                if self._panel_visible.get("terminal", True):
                    terminal.size_hint_y = 1
            else:
                editor.size_hint_y = None
                editor.height = 0
                editor.opacity = 0
                # Terminal now fills the whole left column
                terminal.size_hint_y = 1

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
