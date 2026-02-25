import kivy
from kivy.app import App
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout

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
        self.ids.code_input.text = (
            '# Write Python here\ndef foo():\n    print("test")\nfoo()'
        )
        self.ids.code_input.bind(text=self._update_line_numbers)
        self.ids.code_input.bind(scroll_y=self._sync_scroll)
        self._update_line_numbers(self.ids.code_input, self.ids.code_input.text)

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


class PythonVisualizer(App):
    def build(self):
        return RootLayout()


if __name__ == "__main__":
    PythonVisualizer().run()
