from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .converter import Cancelled
from .workflow import convert
from . import __version__


class App:
    def __init__(self, root):
        self.root = root
        self.paths = []
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        root.title('Blender Batch EXR ' + __version__)
        root.geometry('840x620')
        root.minsize(700, 520)
        root.configure(bg='#202226')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background='#202226', foreground='#eeeeee', fieldbackground='#2c3035', font=('Segoe UI', 10))
        style.configure('TButton', padding=7, background='#383d44')
        style.map('TButton', background=[('active', '#4b5560'), ('disabled', '#292c31')], foreground=[('disabled', '#777d85')])
        style.map('TCheckbutton', background=[('active', '#202226')])
        style.map('TCombobox', fieldbackground=[('readonly', '#2c3035')], foreground=[('readonly', '#eeeeee')])
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Blender Batch EXR', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='EXR to layered PSD • RLAYER4 finishing • No Photoshop required').pack(anchor='w', pady=(3, 16))
        bar = ttk.Frame(frame)
        bar.pack(fill='x')
        self.controls = []
        for title, command in [('Add EXRs…', self.add_files), ('Add folder…', self.add_folder), ('Remove selected', self.remove), ('Clear', self.clear)]:
            button = ttk.Button(bar, text=title, command=command)
            button.pack(side='left', padx=(0, 8))
            self.controls.append(button)
        self.listbox = tk.Listbox(frame, selectmode='extended', height=8, bg='#17191c', fg='#eeeeee', selectbackground='#376586', relief='flat', highlightthickness=0)
        self.listbox.pack(fill='both', expand=True, pady=12)
        output = ttk.Frame(frame)
        output.pack(fill='x')
        ttk.Label(output, text='Output folder').pack(side='left', padx=(0, 12))
        self.output = tk.StringVar()
        entry = ttk.Entry(output, textvariable=self.output)
        entry.pack(side='left', fill='x', expand=True)
        self.controls.append(entry)
        button = ttk.Button(output, text='Browse…', command=self.browse_output)
        button.pack(side='left', padx=(8, 0))
        self.controls.append(button)
        ttk.Label(frame, text='Leave blank to save beside each EXR. Existing files are never overwritten.', foreground='#afb5bc').pack(anchor='w', pady=(5, 10))
        self.finish = tk.BooleanVar(value=True)
        finishing = ttk.Checkbutton(frame, text='Apply RLAYER4 finishing (8-bit sRGB) — disable for raw 32-bit HDR', variable=self.finish)
        finishing.pack(anchor='w', pady=(0, 8))
        self.controls.append(finishing)
        options = ttk.Frame(frame)
        options.pack(fill='x')
        self.masks = tk.BooleanVar(value=True)
        self.unpremultiply = tk.BooleanVar(value=True)
        for text, variable in [('Cryptomatte masks', self.masks), ('Unpremultiply RGB', self.unpremultiply)]:
            cb = ttk.Checkbutton(options, text=text, variable=variable)
            cb.pack(side='left', padx=(0, 18))
            self.controls.append(cb)
        self.format = tk.StringVar(value='auto')
        combo = ttk.Combobox(options, textvariable=self.format, values=['auto', 'psd', 'psb'], state='readonly', width=7)
        combo.pack(side='right')
        self.controls.append(combo)
        ttk.Label(options, text='Format  ').pack(side='right')
        self.logbox = tk.Text(frame, height=7, bg='#17191c', fg='#bdc5cf', relief='flat', font=('Consolas', 9), state='disabled', wrap='word')
        self.logbox.pack(fill='both', pady=12)
        self.progress = ttk.Progressbar(frame, mode='indeterminate')
        self.progress.pack(fill='x')
        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', pady=(12, 0))
        self.status = tk.StringVar(value='Ready — add EXR files to begin')
        ttk.Label(bottom, textvariable=self.status).pack(side='left')
        self.start_button = ttk.Button(bottom, text='Convert batch', command=self.start)
        self.start_button.pack(side='right')
        self.stop_button = ttk.Button(bottom, text='Cancel', command=self.stop, state='disabled')
        self.stop_button.pack(side='right', padx=8)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def add(self, paths):
        for path in paths:
            path = Path(path).resolve()
            if path not in self.paths:
                self.paths.append(path)
                self.listbox.insert('end', str(path))
        self.status.set(f'{len(self.paths)} files queued')

    def add_files(self):
        self.add(filedialog.askopenfilenames(filetypes=[('OpenEXR', '*.exr')]))

    def add_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.add(sorted(Path(folder).glob('*.exr')))

    def remove(self):
        for i in reversed(self.listbox.curselection()):
            del self.paths[i]
            self.listbox.delete(i)

    def clear(self):
        self.paths.clear()
        self.listbox.delete(0, 'end')

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output.set(path)

    def start(self):
        if not self.paths or self.busy:
            return
        self.busy = True
        self.cancel.clear()
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        for control in self.controls:
            control.configure(state='disabled')
        self.progress.start(12)
        settings = dict(output_dir=self.output.get().strip() or None, masks=self.masks.get(),
                        unpremultiply=self.unpremultiply.get(), format=self.format.get(),
                        workflow='rlayer4' if self.finish.get() else 'raw')
        threading.Thread(target=self.worker, args=(list(self.paths), settings), daemon=True).start()

    def worker(self, paths, settings):
        done = failed = skipped = 0
        for i, path in enumerate(paths):
            if self.cancel.is_set():
                break
            self.events.put(('status', f'File {i + 1} of {len(paths)}: {path.name}'))
            try:
                convert(path, **settings, cancel=self.cancel, log=lambda s: self.events.put(('log', s)))
                done += 1
            except Cancelled:
                break
            except FileExistsError as error:
                skipped += 1
                self.events.put(('log', 'SKIPPED: ' + str(error)))
            except Exception as error:
                failed += 1
                self.events.put(('log', 'ERROR: ' + str(error)))
        self.events.put(('done', f'{"Cancelled" if self.cancel.is_set() else "Finished"}: {done} saved, {skipped} skipped, {failed} failed'))

    def stop(self):
        self.cancel.set()
        self.status.set('Cancelling — waiting for the current read/write step…')
        self.stop_button.configure(state='disabled')

    def poll(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind in ('status', 'done'):
                    self.status.set(message)
                else:
                    self.logbox.configure(state='normal')
                    self.logbox.insert('end', message + '\n')
                    self.logbox.see('end')
                    self.logbox.configure(state='disabled')
                if kind == 'done':
                    self.busy = False
                    self.progress.stop()
                    self.start_button.configure(state='normal')
                    self.stop_button.configure(state='disabled')
                    for control in self.controls:
                        control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            self.stop()
            messagebox.showinfo('Finishing cancellation', 'Please wait for cancellation to finish, then close the window.')
        else:
            self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
