import kivy
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.boxlayout import BoxLayout

Builder.load_file("interface.kv")


class RootLayout(BoxLayout):
    pass


class PythonVisualizer(App):
    def build(self):
        return RootLayout()


if __name__ == "__main__":
    PythonVisualizer().run()
