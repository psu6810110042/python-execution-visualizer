import os
import pty
import select
import shlex
import subprocess
import threading
import time

from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivy.utils import get_color_from_hex


class InteractiveTerminal(MDBoxLayout):
    output_text = StringProperty("")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self._process = None
        self._master_fd = None
        self._read_thread = None
        self._stop_event = threading.Event()
        self._executor = None
        
        # Build UI via code instead of KV so we can drop it in easily
        from kivy.lang import Builder
        Builder.load_string('''
<InteractiveTerminal>:
    MDBoxLayout:
        orientation: 'vertical'
        md_bg_color: utils.get_color_from_hex('#1e1e1e')
        padding: '5dp'
        
        ScrollView:
            id: scroll_view
            do_scroll_x: False # Allow long commands and outputs to wrap
            do_scroll_y: True
            
            TextInput:
                id: history_input
                text: root.output_text
                readonly: True
                background_color: 0, 0, 0, 0
                foreground_color: utils.get_color_from_hex('#d4d4d4')
                font_name: 'RobotoMono-Regular'
                font_size: '13sp'
                size_hint_y: None
                height: max(self.minimum_height, scroll_view.height)
                cursor_color: 0, 0, 0, 0
                padding: ['10dp', '10dp']
                # This fixes the crazy spacing: use a multiline non-wrapping text input
                use_bubble: False
                use_handles: False
                selection_color: utils.get_color_from_hex('#264f78')
                
        MDBoxLayout:
            size_hint_y: None
            height: '35dp'
            md_bg_color: utils.get_color_from_hex('#252526')
            padding: ['10dp', '0dp']
            
            MDLabel:
                text: ">"
                font_name: 'RobotoMono-Regular'
                font_size: '13sp'
                theme_text_color: "Custom"
                text_color: utils.get_color_from_hex('#a6e22e') # Green prompt
                size_hint_x: None
                width: '15dp'
                
            TextInput:
                id: cmd_input
                multiline: False
                background_color: 0, 0, 0, 0
                foreground_color: utils.get_color_from_hex('#d4d4d4')
                font_name: 'RobotoMono-Regular'
                font_size: '13sp'
                cursor_color: utils.get_color_from_hex('#d4d4d4')
                selection_color: utils.get_color_from_hex('#264f78')
                padding: [0, '10dp'] # Align properly with prompt
                on_text_validate: root._on_submit_cmd()
''')

    def send_interrupt(self):
        """Sends a Ctrl+C (SIGINT) to the running process or visualizer."""
        self._append_output("^C\n")
        
        # If visualizer is running, kill it
        if self._executor:
            self._executor.stop()
        else:
            # Send SIGINT character (0x03) to the pty so the shell kills the foreground job
            if self._master_fd:
                os.write(self._master_fd, b'\x03')

    def start_shell(self):
        """Starts a background shell process using a pseudo-terminal (pty)."""
        if self._process is not None:
            return

        shell_cmd = '/bin/bash' # Bash is more stable for dumb terminals than user-configured Zsh
        env = os.environ.copy()
        env['TERM'] = 'dumb'    # Stop advanced line redrawing and colors
        env['PS1'] = '$ '       # Setup a simple clean prompt
        
        self._master_fd, slave_fd = pty.openpty()
        
        self._process = subprocess.Popen(
            [shell_cmd, '--noediting'], # Prevent readline echo loops
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            text=True,
            bufsize=1,
            close_fds=True,
            env=env
        )
        os.close(slave_fd)
        
        self._stop_event.clear()
        self._read_thread = threading.Thread(target=self._read_from_pty, daemon=True)
        self._read_thread.start()
        
        # Small delay to let the shell prompt print
        Clock.schedule_once(lambda dt: self.ids.cmd_input.focus, 0.5)

    def stop_shell(self):
        """Stops the running shell."""
        self._stop_event.set()
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

    def _read_from_pty(self):
        """Continuously reads output from the shell pseudo-terminal."""
        while not self._stop_event.is_set() and self._master_fd is not None:
            r, _, _ = select.select([self._master_fd], [], [], 0.1)
            if self._master_fd in r:
                try:
                    data = os.read(self._master_fd, 4096).decode('utf-8', errors='replace')
                    if data:
                        Clock.schedule_once(lambda dt, text=data: self._append_output(text))
                except OSError:
                    break

    @mainthread
    def _append_output(self, text):
        import re
        
        # 1. Standard ANSI escape sequences (colors, cursor movements)
        # Matches ESC [ ... m or other command letters
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        # 2. OSC sequences (window titles, icons, marks usually ending in \x07 or \x1b\\)
        # Matches ESC ] ... BEL or ESC ] ... ESC \
        osc_escape = re.compile(r'\x1B\].*?(?:\x07|\x1B\\)')
        
        # 3. Handle raw bell characters and other control characters that don't belong
        # Remove literal \x07 (bell) that sometimes sneaks through, but keep \n and \t
        control_chars = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]')
        
        clean_text = osc_escape.sub('', text)
        clean_text = ansi_escape.sub('', clean_text)
        clean_text = control_chars.sub('', clean_text).replace('\r\n', '\n')
        
        self.output_text += clean_text
        # Auto scroll to bottom
        self.ids.scroll_view.scroll_y = 0

    def restart_terminal(self):
        """Forcefully stops the current shell and starts a fresh one."""
        self.stop_shell()
        self.clear()
        self.start_shell()

    def _on_submit_cmd(self):
        """Handles when the user presses Enter in the TextInput."""
        cmd = self.ids.cmd_input.text
        self.ids.cmd_input.text = ""
        
        if not cmd.strip() and not self._executor:
            return
            
        # Intercept "clear" command
        if cmd.strip() == "clear":
            self.clear()
            Clock.schedule_once(lambda dt: self._refocus_input(), 0.1)
            return

        # Intercept "exit" command to kill the running script or shell
        if cmd.strip() == "exit":
            if self._executor:
                # Just kill the visualizer
                self.send_interrupt()
            else:
                # Kill the background shell
                self.send_interrupt()
                self.restart_terminal()
            Clock.schedule_once(lambda dt: self._refocus_input(), 0.1)
            return
            
        # Check if the visualizer is currently waiting for input()
        if self._executor and self._executor.waiting_for_input:
            self._append_output(cmd + "\n")
            self._executor.provide_input(cmd)
        else:
            # Send to shell
            if self._master_fd:
                os.write(self._master_fd, f"{cmd}\n".encode('utf-8'))
            
        Clock.schedule_once(lambda dt: self._refocus_input(), 0.1)
        
    def _refocus_input(self):
        self.ids.cmd_input.focus = True

    def clear(self):
        self.output_text = ""
        
    def register_executor(self, executor_instance):
        """Registers the active visualizer executor so we can route inputs to it."""
        self._executor = executor_instance
        
    def unregister_executor(self):
        """Removes the visualizer executor."""
        if self._executor and self._executor.waiting_for_input:
            self._executor.provide_input("") # Unblock it if it was waiting
        self._executor = None
