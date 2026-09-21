import sys


def smoke_test(folder):
    """Exercise the packaged native reader, writer and Tk without showing a window."""
    import json
    from pathlib import Path
    import tkinter as tk
    import numpy as np
    import OpenEXR
    from blender_batch_exr.converter import convert
    from blender_batch_exr.gui import App
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.withdraw()
    App(root)
    root.update()
    root.destroy()
    source = folder / 'packaged-smoke.exr'
    OpenEXR.File({}, {c: np.full((3, 4), v, np.float32) for c, v in [('R', 2), ('G', .5), ('B', .25), ('A', 1)]}).write(str(source))
    result = convert(source)
    (folder / 'result.json').write_text(json.dumps({'ok': True, 'output': str(result), 'size': result.stat().st_size}), encoding='utf-8')


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        smoke_test(sys.argv[2])
    else:
        from blender_batch_exr.gui import run
        run()

if __name__ == '__main__':
    main()
