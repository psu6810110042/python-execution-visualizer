import os
import re

def count_metrics():
    callbacks = 0
    widgets = 0
    
    # regexes
    kv_callback_re = re.compile(r'^\s*on_[a-z_]+\s*:', re.MULTILINE)
    py_bind_re = re.compile(r'\.bind\(')
    py_clock_re = re.compile(r'Clock\.schedule')
    
    kv_widget_def_re = re.compile(r'^<[A-Za-z0-9_@]+>:', re.MULTILINE)
    kv_widget_inst_re = re.compile(r'^\s+([A-Z][a-zA-Z0-9_]*):', re.MULTILINE)
    py_widget_class_re = re.compile(r'class\s+[A-Za-z0-9_]+\s*\([^)]*(Widget|Layout|Button|Label|Screen|App|MD|BoxLayout|FloatLayout|Splitter)[^)]*\):')

    for root, dirs, files in os.walk('.'):
        if '.git' in root or '__pycache__' in root or '.venv' in root or '.pytest_cache' in root:
            continue
            
        for f in files:
            path = os.path.join(root, f)
            if not (f.endswith('.py') or f.endswith('.kv')):
                continue
                
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    
                    if f.endswith('.kv'):
                        callbacks += len(kv_callback_re.findall(content))
                        widgets += len(kv_widget_def_re.findall(content))
                        for match in kv_widget_inst_re.findall(content):
                            if match not in ('Color', 'Rectangle', 'Line', 'Ellipse', 'RoundedRectangle'):
                                widgets += 1
                                
                    elif f.endswith('.py'):
                        callbacks += len(py_bind_re.findall(content))
                        callbacks += len(py_clock_re.findall(content))
                        widgets += len(py_widget_class_re.findall(content))
            except Exception as e:
                pass

    print(f"Callbacks: {callbacks}")
    print(f"Widgets: {widgets}")

if __name__ == '__main__':
    count_metrics()
