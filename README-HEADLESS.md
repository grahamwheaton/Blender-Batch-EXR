# Blender Batch EXR — headless usage (v0.3.0)

Convert EXRs without opening a window, Photoshop or Blender. The output uses the same EXR-IO-compatible layers and Cryptomatte masks as the graphical app.

## Quick start

Extract the Windows x64 release ZIP. Use **BlenderBatchEXR-CLI.exe** for scripts, terminals and scheduled tasks. No Python installation is needed.

In PowerShell, change to the extracted folder, then run:

```powershell
.\BlenderBatchEXR-CLI.exe "D:\Renders\image.exr" -o "D:\Converted"
```

Convert every EXR directly inside a folder:

```powershell
.\BlenderBatchEXR-CLI.exe "D:\Renders" -o "D:\Converted"
```

Include subfolders and write a log:

```powershell
.\BlenderBatchEXR-CLI.exe "D:\Renders" --recursive -o "D:\Converted" --log "D:\Logs\exr-batch.log"
```

Files run sequentially. Progress is printed in the terminal. Errors are reported and the batch continues with the next file. Originals are never changed, and existing PSD/PSB files are never overwritten.

## Options

| Option | Behaviour |
| --- | --- |
| `inputs` | One or more EXR file paths or folders, separated by spaces. Quote paths containing spaces. |
| `-o`, `--output` | Output folder, created if needed. Omit to save beside each EXR. |
| `--recursive` | Include EXRs in subfolders of each input folder. |
| `--format auto` | Default: PSD, falling back to PSB when required by file size or dimensions. |
| `--format psd` | Require PSD; report an error if limits are exceeded. |
| `--format psb` | Always create PSB files. |
| `--no-masks` | Keep raw Cryptomatte data instead of generating named masks. |
| `--keep-premultiplied` | Disable RGB unpremultiplication. Default settings match the tested EXR-IO import. |
| `--log "path"` | Append progress, errors and a batch summary to a UTF-8 file. Parent folders are created. |
| `--quiet` | Hide console progress. Console errors and file logging remain enabled. |
| `--skip-existing` | Skip existing outputs without making the batch fail. Useful for rerunning a completed batch. |
| `--headless` | Explicit headless mode; optional for the CLI executable, which never starts the GUI. |
| `--help` | Print usage and exit. |
| `--version` | Print the version and exit. |

Pass actual file/folder paths rather than wildcard patterns such as `*.exr`.

## Multiple files and repeat runs

```powershell
.\BlenderBatchEXR-CLI.exe "D:\Renders\Camera 1.exr" "D:\Renders\Camera 2.exr" -o "D:\Converted"
.\BlenderBatchEXR-CLI.exe "D:\Renders" --recursive --skip-existing --log "D:\Logs\exr-batch.log"
```

Repeated references to the same input are processed once. A shared output folder uses source basenames: `RoomA\frame.exr` and `RoomB\frame.exr` would both target `frame.psd`. To keep both, omit `-o` so files are saved beside their respective sources, choose separate output folders, or use unique EXR names. Recursive conversion does not reproduce the directory tree inside a shared output folder.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All files converted successfully, or existing outputs were skipped with `--skip-existing`. |
| `1` | A conversion/input error occurred, a folder contained no EXRs, or an existing output was skipped without `--skip-existing`. |
| `2` | Invalid arguments, no input arguments, or a log file could not be opened. |
| `130` | Interrupted with Ctrl+C. |

PowerShell waits for the CLI executable and exposes its result as `$LASTEXITCODE`:

```powershell
& "C:\Tools\BlenderBatchEXR\BlenderBatchEXR-CLI.exe" "D:\Renders" -o "D:\Converted" --skip-existing
if ($LASTEXITCODE -ne 0) {
    throw "EXR conversion failed. Check the log."
}
```

From a Windows batch file:

```bat
@echo off
"C:\Tools\BlenderBatchEXR\BlenderBatchEXR-CLI.exe" "D:\Renders" -o "D:\Converted" --log "D:\Logs\exr-batch.log" --skip-existing
exit /b %ERRORLEVEL%
```

## Run with no visible console

The regular **BlenderBatchEXR.exe** also accepts the same arguments. With `--headless` and input paths it does not load the GUI. Since it is a Windows GUI executable, use `Start-Process -Wait -PassThru` to wait reliably and obtain its exit code. Use `--log` because this executable has no console output.

```powershell
$tool = 'C:\Tools\BlenderBatchEXR\BlenderBatchEXR.exe'
$arguments = '--headless "D:\My Renders" -o "D:\Converted" --log "D:\Logs\exr-batch.log" --skip-existing'
$job = Start-Process -FilePath $tool -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
if ($job.ExitCode -ne 0) { throw "Conversion failed: exit $($job.ExitCode)" }
```

Running the regular executable without arguments opens the GUI. Running the CLI executable without inputs prints an argument error and exits; it never opens a file picker or GUI.

## Windows Task Scheduler

Create a task with an action **Start a program**:

- **Program/script:** `C:\Tools\BlenderBatchEXR\BlenderBatchEXR-CLI.exe`
- **Add arguments:** `"D:\Renders" -o "D:\Converted" --recursive --skip-existing --log "D:\Logs\exr-batch.log"`
- **Start in:** `C:\Tools\BlenderBatchEXR`

Choose your trigger and an account that can read the EXRs and write to the output/log folders. For unattended runs, choose **Run whether user is logged on or not**. Use absolute paths; mapped drive letters may be unavailable to a scheduled task, so use an accessible UNC path for network folders. Set concurrent task instances to **Do not start a new instance** to avoid overlapping batches.

This is a one-shot batch, not a folder watcher. Schedule it after rendering has finished; it does not wait for Blender to finish writing an EXR. A successful task result is `0x0`.

## Run from Python source

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m blender_batch_exr --headless "D:\Renders" -o "D:\Converted" --log "D:\Logs\exr-batch.log"
```

The dedicated CLI build excludes Tk. Neither headless path imports the graphical interface. Large multilayer EXRs still require enough RAM and disk space. See [README.md](README.md) for colour handling, PSD/PSB limits and supported EXR features.
