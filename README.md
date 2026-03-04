# Python Execution Visualizer

A powerful, real-time Python code visualization tool built with Kivy and KivyMD. This application allows developers and learners to walk through Python code step-by-step, observing variable states, the call stack, and terminal output in real-time.

![UI Overview](https://via.placeholder.com/800x450?text=Python+Execution+Visualizer+UI)

## 🚀 Key Features

- **Real-time Visualization**: Watch code execute line-by-line with high-performance tracing.
- **Interactive Input Support**: Handle `input()` calls directly from the built-in terminal.
- **Variable Inspection**: Track local and global variable changes at every step.
- **Call Stack Tracking**: Visualize the active function stack and frame transitions.
- **Integrated Terminal**: A full-featured terminal emulator for program output and user interaction.
- **Scrubbing & Playback**: Move backwards and forwards through the execution history.
- **Execution Analytics**: Track how many times each line was executed (execution badge).

## 🏗️ Architecture

The project is divided into a clear separation of concerns between the core execution engine and the graphical interface.

### Core Engine (`/core`)
- **`tracer.py`**: Uses `sys.settrace` to instrument Python code. It captures line events, return values, call stack transitions, and serialized variable states. It features an `on_step` callback for streaming updates.
- **`executor.py`**: Manages the execution environment. It handles code parsing, timeout enforcement, and provides a "mock" `input()` function that bridges the background execution thread with the UI terminal input.
- **`terminal.py`**: Implements a terminal emulator using `pyte` and handles low-level PTY (pseudo-terminal) interactions for both Windows and Unix systems. It synchronizes its state with the tracer's stdout buffer.

### UI Layers (`/`)
- **`main.py`**: The entry point and main application controller. It manages the Kivy event loop, thread safety (using `Clock.schedule_once`), and updates the UI components based on incoming trace steps.
- **Kivy Layouts**: Uses a modular layout system for the code editor, variable tree, call stack, and terminal panels.

## 🛠️ Technical Implementation Details

### Interactive Input Mechanism
One of the most complex features is the synchronous `input()` support within an asynchronous UI.
1. When the executed code calls `input()`, it triggers our `mock_input` function in a background thread.
2. `mock_input` writes the prompt to the stdout buffer and blocks on a `threading.Event`.
3. The UI detects the waiting state and focuses the terminal.
4. As the user types in the terminal, characters are streamed back to the tracer's buffer and the UI is refreshed globally.
5. Upon pressing **Enter**, the `Event` is set, the value is returned to the Python program, and execution continues.

### Terminal Sync Strategy
To ensure the terminal always looks correct (especially during real-time input), we use a **Full Sync** strategy. Instead of just appending text, the UI calls `sync_with_stdout(full_text)`, which resets the terminal emulator and re-feeds the entire trace history. This prevents alignment issues and ensures that backspaces/edits during input are rendered perfectly.

## 🏃 Getting Started

### Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip`

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/python-execution-visualizer.git
   cd python-execution-visualizer
   ```
2. Install dependencies:
   ```bash
   uv sync
   ```

### Running the App
```bash
uv run main.py
```

## 📝 Example Code to Try
Try running this in the visualizer to see the interactive input in action:
```python
def greet():
    name = input("What is your name? ")
    age = input("How old are you? ")
    print(f"Hello {name}, you are {age}!")

greet()
```

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## 📜 License
This project is licensed under the MIT License.
