import os
import re
import select
import shlex
import subprocess
import threading
import time

if os.name == "nt":
    from winpty import PtyProcess
else:
    import pty
    import termios

from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.properties import StringProperty, ObjectProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.utils import get_color_from_hex
from kivy.lang import Builder
import pyte


PYTE_COLORS = {
    "black": "000000",
    "red": "cc0000",
    "green": "4e9a06",
    "brown": "c4a000",
    "blue": "3465a4",
    "magenta": "75507b",
    "cyan": "06989a",
    "lightgray": "d3d7cf",
    "darkgray": "555753",
    "lightred": "ef2929",
    "lightgreen": "8ae234",
    "yellow": "fce94f",
    "lightblue": "729fcf",
    "lightmagenta": "ad7fa8",
    "lightcyan": "34e2e2",
    "white": "eeeeec",
    "brightblack": "555753",
    "brightred": "ef2929",
    "brightgreen": "8ae234",
    "brightbrown": "fce94f",
    "brightblue": "729fcf",
    "brightmagenta": "ad7fa8",
    "brightcyan": "34e2e2",
    "brightwhite": "ffffff",
    "default": "d4d4d4"
}


class InteractiveTerminal(MDBoxLayout):
    output_text = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self._process = None
        self._master_fd = None  # For Unix
        self._win_pty = None  # For Windows
        self._read_thread = None
        self._stop_event = threading.Event()
        self._executor = None
        self._keyboard = None
        self.on_focus_changed = None  # Callback: fn(focused: bool)
        
        # Pyte Emulator State
        self._lines = 24
        self._columns = 80
        # Pyte screen buffer and history stream
        self._screen = pyte.HistoryScreen(self._columns, self._lines, history=1000)
        self._stream = pyte.Stream(self._screen)

        Builder.load_string(
            """
<InteractiveTerminal>:
    md_bg_color: utils.get_color_from_hex('#1e1e1e')
    padding: '5dp'
    
    ScrollView:
        id: scroll_view
        do_scroll_x: True
        do_scroll_y: True
        
        AnchorLayout:
            size_hint: None, None
            size: max(display.texture_size[0], scroll_view.width), max(display.texture_size[1], scroll_view.height)
            anchor_x: 'left'
            anchor_y: 'top'

            Label:
                id: display
                markup: True
                font_name: 'RobotoMono-Regular'
                font_size: '13sp'
                text: root.output_text
                size_hint: None, None
                size: self.texture_size
                color: utils.get_color_from_hex('#d4d4d4')
"""
        )

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._request_keyboard()
        return super().on_touch_down(touch)

    def _request_keyboard(self):
        # Always release the old keyboard first (in case _keyboard_closed wasn't
        # called, e.g. when code_input stole focus without going through our callback)
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard = None
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        if callable(self.on_focus_changed):
            self.on_focus_changed(True)

    def _keyboard_closed(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_key_down)
            self._keyboard = None
            if callable(self.on_focus_changed):
                self.on_focus_changed(False)

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        key = keycode[0]
        key_str = keycode[1]

        # When in visualization mode (code readonly), forward step-navigation keys to root
        try:
            from kivymd.app import MDApp
            root = MDApp.get_running_app().root
            if hasattr(root, 'ids') and root.ids.code_input.readonly:
                if key == 275:  # RIGHT arrow -> next step
                    root.step_visualization(1)
                    return True
                elif key == 276:  # LEFT arrow -> prev step
                    root.step_visualization(-1)
                    return True
                elif key == 32:  # SPACE -> play/pause
                    if root.trace_data:
                        root.toggle_play(root.ids.btn_play)
                    return True
                elif key == 273:  # UP arrow -> increase speed
                    slider = root.ids.speed_slider
                    slider.value = min(slider.max, round(slider.value + 0.1, 1))
                    return True
                elif key == 274:  # DOWN arrow -> decrease speed
                    slider = root.ids.speed_slider
                    slider.value = max(slider.min, round(slider.value - 0.1, 1))
                    return True
        except Exception:
            pass

        if not self._executor and not self._win_pty and not self._process:
            return True
        
        # Ignore pure modifier keys
        if key_str in ['ctrl', 'lctrl', 'rctrl', 'alt', 'lalt', 'ralt', 'super', 'capslock', 'numlock', 'scrolllock']:
            return True

        # Forward panel-toggle and font-size shortcuts to root even when terminal is focused
        if 'ctrl' in modifiers:
            from kivymd.app import MDApp
            root = MDApp.get_running_app().root
            if key == ord('1'):
                root.toggle_panel('terminal')
                return True
            if key == 96:  # backtick
                root.toggle_panel('right')
                return True
            if key == ord('2'):
                root.toggle_panel('editor')
                return True
            # Font size: Ctrl+= / Ctrl++ increase, Ctrl+- decrease, Ctrl+0 reset
            if key in (61, 43):  # '=' or '+'
                root.change_font_size(+1)
                return True
            if key == 45:  # '-'
                root.change_font_size(-1)
                return True
            if key == ord('0'):
                root.reset_font_size()
                return True

        # Determine VT sequence or character to send
        vt_seq = None
        
        # Arrows
        if key == 273: vt_seq = "\x1b[A" # UP
        elif key == 274: vt_seq = "\x1b[B" # DOWN
        elif key == 275: vt_seq = "\x1b[C" # RIGHT
        elif key == 276: vt_seq = "\x1b[D" # LEFT
        # Navigation
        elif key == 278: vt_seq = "\x1b[H" # HOME
        elif key == 279: vt_seq = "\x1b[F" # END
        elif key == 280: vt_seq = "\x1b[5~" # PAGE UP
        elif key == 281: vt_seq = "\x1b[6~" # PAGE DOWN
        # Special keys
        elif key == 8: 
            if os.name == "nt": vt_seq = "\x08" # Windows expects BS
            else: vt_seq = "\x7f" # Unix expects DEL for Backspace
        elif key == 13: # ENTER / RETURN
            if os.name == "nt" and self._win_pty:
                vt_seq = "\r\n"
            else:
                vt_seq = "\r"
        elif key == 27: vt_seq = "\x1b" # ESC
        elif key == 9: vt_seq = "\t" # TAB
        elif key == 127: vt_seq = "\x1b[3~" # DEL
        elif 'ctrl' in modifiers and key_str == 'c':
            vt_seq = "\x03" # SIGINT
        elif 'ctrl' in modifiers and key_str == 'd':
            vt_seq = "\x04" # EOF
        elif 'ctrl' in modifiers and key_str == 'l':
            vt_seq = "\x0c" # CLEAR
        elif text:
            # Regular typing
            vt_seq = text
            
        if vt_seq:
            self._write_to_pty(vt_seq)
            
        return True # Handled

    def _write_to_pty(self, data):
        # Route to executor if it's waiting for input (basic intercept)
        if self._executor and self._executor.waiting_for_input:
            # We don't echo to _append_output directly because we lack a full input() buffer,
            # but wait, standard python input() blocks. We intercept char by char?
            # Easiest: if executor expects input, we should accumulate until \\n.
            if not hasattr(self, '_input_buffer'):
                self._input_buffer = ""
            
            if data in ("\r", "\n", "\r\n"):
                # submit buffer
                cmd = self._input_buffer
                self._input_buffer = ""
                self._append_output("\r\n")
                self._executor.provide_input(cmd)
            elif data == "\x08": # bs
                if len(self._input_buffer) > 0:
                    self._input_buffer = self._input_buffer[:-1]
                    self._append_output("\x08 \x08")
            else:
                self._input_buffer += data
                self._append_output(data)
            return

        # Normal PTY processing
        try:
            if os.name == "nt" and self._win_pty:
                self._win_pty.write(data)
            elif self._master_fd is not None:
                os.write(self._master_fd, data.encode("utf-8"))
        except Exception:
            pass

    def send_interrupt(self):
        """Sends a Ctrl+C (SIGINT) to the running process or visualizer."""
        self._append_output("^C\n")

        if self._executor:
            self._executor.stop()
        else:
            self._write_to_pty("\x03")

    def start_shell(self):
        """Starts a background shell process using a pseudo-terminal (pty)."""
        if self._process is not None or self._win_pty is not None:
            return

        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        if os.name == "nt":
            # --- Windows ---
            shell = "powershell.exe"
            self._win_pty = PtyProcess.spawn(shell, env=env, dimensions=(self._lines, self._columns))
            self._stop_event.clear()
            self._read_thread = threading.Thread(
                target=self._read_windows_pty, daemon=True
            )
        else:
            # --- Unix ---
            shell_cmd = "/bin/bash"
            self._master_fd, slave_fd = pty.openpty()
            self._process = subprocess.Popen(
                [shell_cmd],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=True,
                bufsize=1,
                close_fds=True,
                env=env,
            )
            os.close(slave_fd)
            self._stop_event.clear()
            self._read_thread = threading.Thread(
                target=self._read_unix_pty, daemon=True
            )

        self._read_thread.start()
        # Auto-focus when shell starts
        Clock.schedule_once(lambda dt: self._request_keyboard(), 0.5)

    def stop_shell(self):
        """Stops the running shell."""
        self._stop_event.set()

        if os.name == "nt" and self._win_pty:
            self._win_pty.terminate()
            self._win_pty = None
        else:
            if self._process:
                self._process.terminate()
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                self._process = None
            if self._master_fd:
                os.close(self._master_fd)
                self._master_fd = None

    def _read_unix_pty(self):
        """Continuously reads output from the Unix shell pseudo-terminal."""
        while not self._stop_event.is_set() and self._master_fd is not None:
            r, _, _ = select.select([self._master_fd], [], [], 0.1)
            if self._master_fd in r:
                try:
                    data = os.read(self._master_fd, 4096).decode(
                        "utf-8", errors="replace"
                    )
                    if data:
                        Clock.schedule_once(
                            lambda dt, text=data: self._append_output(text)
                        )
                except OSError:
                    break

    def _read_windows_pty(self):
        """Continuously reads output from the Windows winpty process."""
        while not self._stop_event.is_set() and self._win_pty is not None:
            try:
                if self._win_pty.isalive():
                    data = self._win_pty.read(4096)
                    if data:
                        Clock.schedule_once(
                            lambda dt, text=data: self._append_output(text)
                        )
                else:
                    break
            except EOFError:
                break
            # Small sleep to prevent tight looping since winpty read can block
            time.sleep(0.01)

    @mainthread
    def _append_output(self, text):
        # Feed exactly into pyte emulator
        self._stream.feed(text)
        self._render_screen()

    def _render_screen(self):
        lines = []
        
        def process_line(screen_line_dict):
            fmt_line = ""
            current_fg = None
            current_bg = None
            current_text = ""
            
            def close_tags():
                res = ""
                if current_text:
                    if current_bg: res += f"[backcolor={current_bg}]"
                    if current_fg: res += f"[color={current_fg}]"
                    res += current_text
                    if current_fg: res += "[/color]"
                    if current_bg: res += "[/backcolor]"
                return res

            for x in range(self._columns):
                char = screen_line_dict.get(x)
                if not char:
                    fg, bg, text = None, None, " "
                else:
                    fg = PYTE_COLORS.get(char.fg, char.fg) if char.fg != "default" else None
                    bg = PYTE_COLORS.get(char.bg, char.bg) if char.bg != "default" else None
                    
                    text = char.data
                    # Custom minimal markup escape to dodge Kivy parser errors
                    text = text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")
                    if not text: text = " "
                
                if fg != current_fg or bg != current_bg:
                    fmt_line += close_tags()
                    current_fg = fg
                    current_bg = bg
                    current_text = text
                else:
                    current_text += text
            
            fmt_line += close_tags()
            return fmt_line

        # Process history that rolled off
        for h_line in self._screen.history.top:
            lines.append(process_line(h_line))
            
        # Determine the last active line to display
        max_y = self._screen.cursor.y
        for y in range(self._lines - 1, max_y, -1):
            line_buf = self._screen.buffer[y]
            if any((char.data.strip() or char.bg != "default") for char in line_buf.values()):
                max_y = y
                break

        # Process active screen up to max_y
        for y in range(max_y + 1):
            line_buf = self._screen.buffer[y]
            # avoid pushing many empty trailing spaces
            lines.append(process_line(line_buf))

        # We must add cursor block. For simplicity, just invert colors at screen.cursor.y, screen.cursor.x
        # But for now, we leave it out or handle it correctly if pyte does it.

        self.output_text = "\n".join(lines)
        
        # Auto scroll to bottom AFTER the label updates its texture size
        Clock.schedule_once(self._scroll_to_bottom, 0.1)

    def _scroll_to_bottom(self, dt=None):
        self.ids.scroll_view.scroll_y = 0

    def restart_terminal(self):
        """Forcefully stops the current shell and starts a fresh one."""
        self.stop_shell()
        self.clear()
        self.start_shell()

    def clear(self):
        self._screen.reset()
        self._screen.history.top.clear()
        self._screen.history.bottom.clear()
        self._render_screen()

    def register_executor(self, executor_instance):
        """Registers the active visualizer executor so we can route inputs to it."""
        self._executor = executor_instance
        self._input_buffer = ""

    def unregister_executor(self):
        """Removes the visualizer executor."""
        if self._executor and self._executor.waiting_for_input:
            self._executor.provide_input("")  # Unblock it if it was waiting
        self._executor = None
        self._input_buffer = ""

    def set_font_size(self, size: int):
        """Update the font size of the terminal display label."""
        try:
            self.ids.display.font_size = f"{size}sp"
        except Exception:
            pass
