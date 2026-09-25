# Blender Batch EXR — RLAYER4

Batch-convert EXRs into finished, layered **8-bit sRGB PSD/PSB** files using the 3D viewer Photoshop watcher's Photoshop-free RLAYER4 workflow. Photoshop, Blender and EXR-IO are not required. Original EXRs are never modified.

## Use

Run `BlenderBatchEXR.exe`, add EXRs or a folder, select an optional output folder, and click **Convert batch**. Leave **Apply RLAYER4 finishing** enabled. Disable it for the original raw 32-bit HDR output. Files are processed sequentially; errors are logged and the batch continues. Existing outputs are skipped, never overwritten. Finished mode checks both PSD and PSB basenames.

Version 0.4.0 includes both the graphical app and a dedicated headless executable.

## Headless use

```powershell
.\BlenderBatchEXR-CLI.exe "D:\Renders" -o "D:\Finished" --recursive --log "D:\Logs\batch.log" --skip-existing
.\BlenderBatchEXR-CLI.exe "D:\Renders" -o "D:\HDR" --workflow raw
```

The default is RLAYER4 finishing (8-bit sRGB). Choose `--workflow raw` for 32-bit HDR. See **[README-HEADLESS.md](README-HEADLESS.md)** for all options, exit codes, fully hidden execution, batch scripts and Task Scheduler setup. No Python installation is needed for the portable executables.

## Finished layer setup

The converter first creates a private temporary 32-bit document, then applies the watcher's Photoshop-free RLAYER4 implementation. Only the finished document is published. Temporary intermediates are removed after success, failure or normal cancellation.

- Visible **COMP** group, top to bottom: AO (Multiply 50%), Gloss (Screen 50%, editable white mask), Image (Soft Light 50%), Diff (Normal), hidden GlossDIR.
- COMP receives a mask from Image transparency, including a black mask for an empty Image pass.
- Hidden **RLAYERS** preserves utility passes and decoded Cryptomatte layers. DecalMask is hidden.
- **Diff and Image are required.** Bare names, `.RGB`/`.RGBA` suffixes and view-layer prefixes are accepted. Ambiguous duplicate passes fail; missing optional passes produce warnings.
- Finishing accepts standard scene-linear sRGB/Rec.709 input only. It converts to 8-bit sRGB and clips HDR values outside 0–1. Other colour primaries fail explicitly; use raw mode to preserve them.

This implements the specific RLAYER4 setup, not arbitrary Photoshop actions. It never launches Photoshop. Small quantization/dithering differences from the Photoshop action are expected. No AgX, Filmic or additional exposure transform is applied.

## Raw HDR option

Disable finishing or pass `--workflow raw` to preserve the original layered 32-bit floating-point workflow. HDR/negative values, pass alpha, Unicode names, display/data windows and supported flat multipart EXRs are retained. A linear ICC profile follows EXR chromaticities (sRGB/Rec.709 when absent). All raw layers start visible; this does not reconstruct compositor blend operations.

Cryptomatte masks use embedded or local sidecar manifests and retain fractional coverage as named white silhouette layers. Disable masks to retain raw Cryptomatte channels. RGB unpremultiplication defaults on for Blender colour passes; disable it for straight RGB input. Deep EXRs, subsampled channels, uint32 image channels and extra mipmap/ripmap levels are unsupported. Keep source EXRs as the authoritative HDR files.

## Format, memory and cancellation

Auto writes PSD, falling back to PSB at the intermediate HDR document's dimension/size limits (30,000 pixels or approximately 2 GB). This conservative choice can produce PSB even when the finished 8-bit file would be smaller. Explicit PSD fails when those limits are exceeded; PSB always produces a large document.

OpenEXR reads the entire source into memory. Finishing additionally uses an in-memory PSD library and needs more RAM than raw conversion. Large production scenes still require a memory/performance trial. Cancel takes effect between processing operations and before publication; an EXR read, composite or serialization must finish its current operation first. A force-killed process can leave temporary staging folders.

## Run from source

Use Python 3.10+ (64-bit) with working Tcl/Tk:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m blender_batch_exr
.\.venv\Scripts\python.exe -m blender_batch_exr "D:\Renders" -o "D:\PSDs"
.\.venv\Scripts\python.exe -m blender_batch_exr "D:\Renders" --recursive --format psb
.\.venv\Scripts\python.exe -m blender_batch_exr "D:\Renders" --workflow raw
```

A shared output folder uses source basenames; duplicates are skipped. CLI exit status is nonzero when any file fails, is skipped, or no EXRs are found; use `--skip-existing` to allow existing-output skips. The CLI executable provides console logs and exit codes. The windowed executable accepts `--headless` and the same conversion options; use `--log` and wait for its process as explained in the headless README.

## Build and validation

Run `Build.ps1` to install dependencies, run tests and build `dist/BlenderBatchEXR.exe` and `dist/BlenderBatchEXR-CLI.exe`. Then run `.\.venv\Scripts\python.exe package_release.py` for the portable ZIP with documentation and licenses.

Tests independently read outputs using psd-tools and cover raw HDR/alpha/Cryptomatte, PSD/PSB, finished layer groups, masks, colour, pass validation, cancellation, cleanup and existing-output protection. The executable's `--smoke-test <empty-folder>` exercises Tk, EXR decoding and finished PSD generation. Photoshop-free finishing is adapted from the local watcher implementation; it is not an EXR-IO redistribution or general Photoshop action interpreter.

Original project: https://github.com/grahamwheaton/Blender-Batch-EXR. MIT license; bundled dependencies retain their own licenses.
