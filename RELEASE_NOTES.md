# v0.4.0 — Headless batch conversion

- Adds BlenderBatchEXR-CLI.exe for terminal, script and scheduled-task use. It never loads the GUI and excludes Tk.
- The regular BlenderBatchEXR.exe now also accepts --headless and conversion arguments.
- Adds UTF-8 log files, quiet mode, batch summaries and explicit exit codes.
- Adds --skip-existing for repeat runs and --version.
- Includes README-HEADLESS.md with examples, options, hidden execution and Task Scheduler instructions.
- Preserves the newer Photoshop-free RLAYER4 workflow as the default; use --workflow raw for original 32-bit HDR output.

Extract the ZIP. Use BlenderBatchEXR.exe for the GUI or BlenderBatchEXR-CLI.exe for headless conversion. No Python, Photoshop, Blender or EXR-IO installation required.
