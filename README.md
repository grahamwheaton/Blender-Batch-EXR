# Blender Batch EXR

Convert Blender OpenEXR files into **layered, 32-bit PSD files** before opening Photoshop. Runs locally on Windows without Photoshop, Blender or EXR-IO installed.

## Download and use

Download **BlenderBatchEXR-Windows-x64.zip** from [Releases](https://github.com/grahamwheaton/Blender-Batch-EXR/releases), extract it and run **BlenderBatchEXR.exe**. No Python installation is required for the portable app.

1. Click **Add EXRs** or **Add folder**. Folder selection includes EXRs directly inside that folder.
2. Choose an output folder, or leave it empty to save beside the originals.
3. Leave **Cryptomatte masks** enabled for named object/material masks.
4. Click **Convert batch**. Open the resulting PSDs in Photoshop when finished.

The originals are never modified. Existing output files are skipped. Conversion failures are reported in the log and the batch continues. **Cancel** stops at the next safe processing step; reading an EXR cannot be interrupted midway. Incomplete outputs are removed during normal cancellation/errors.

## What is preserved

- RGB render passes become separate named layers; scalar passes become grayscale RGB layers. XYZ vector passes are grouped as RGB data.
- RGB pixels remain 32-bit floating point, including HDR values above 1 and negative values. No tone mapping or 8-bit conversion is applied.
- Pass alpha becomes layer transparency. **Unpremultiply RGB** defaults on for Blender's premultiplied colour passes. Disable it when your source contains straight RGB. Colours at zero alpha become zero when unpremultiplying.
- Cryptomatte object/material/asset streams with embedded or local sidecar manifests become named grayscale mask layers. Coverage from all ranks is summed, preserving fractional edges. Only IDs present with positive coverage generate masks.
- Raw Cryptomatte RGB channels and the fourth coverage channel are retained as hidden data layers. Their ID values are not unpremultiplied or used as transparency.
- The Combined pass, or Image pass when available, is the only visible layer. Other passes/masks start hidden. The app does not attempt to rebuild your compositor's blend operations.
- Unicode layer names, EXR display/data windows, and ordinary flat multipart EXRs are supported. Parts must share a display window and colour primaries.

Select a mask layer, copy its grayscale contents, and paste into a Photoshop layer mask as needed. The generated masks are independent pixel layers, not masks automatically attached to the beauty layer.

## PSD versus PSB

**Auto** first writes PSD. If the image exceeds PSD's 30,000-pixel dimension limit or the output approaches 2 GB, it uses Photoshop's large-document **PSB** format. Crossing the size limit during writing triggers a restart as PSB, so select PSB explicitly for files you know are large. PSD and PSB both retain layers and HDR data.

**PSD** requires a file within those limits; otherwise conversion reports an error. **PSB** always writes a large-document file.

## Colour and compatibility

Output is scene-linear RGB. An embedded linear ICC profile is generated from EXR chromaticities; when absent, sRGB/Rec.709 primaries and D65 are assumed. Blender's **AgX/Filmic view transform, exposure, looks, and compositor setup are not baked in**. Consequently it will not necessarily look like Blender's display-rendered preview. This is an HDR editing document, not a display-ready export.

The tool uses the [OpenEXR library](https://github.com/AcademySoftwareFoundation/openexr) directly and writes the [Adobe PSD/PSB format](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/). It does not execute, embed or redistribute [EXR-IO](https://www.exr-io.com/), and is not an exact implementation of all EXR-IO features.

Deep EXRs, subsampled channels, uint32 image channels and extra mipmap/ripmap levels are unsupported. EXR metadata not represented by layers/profile is not copied into the PSD. Keep the original EXRs as the authoritative source.

## Memory and performance

Files are processed sequentially. OpenEXR decompresses an entire file into RAM, so a highly compressed, many-pass EXR can need many gigabytes. Layer data is compressed directly into a temporary file; the app does not hold an additional full PSD in memory. Mask planes are generated on demand. Allow enough free disk space for the Photoshop output, which can be substantially larger than the EXR.

This moves EXR decoding and mask extraction outside Photoshop. Photoshop still needs time and memory to load the resulting layered document; no fixed speed improvement is promised.

## Validation

Automated round-trip tests independently read the output using `psd-tools`, checking HDR/negative values, transparency, Cryptomatte coverage, Unicode names, cropped windows, both formats, cancellation, existing-file protection, and automatic PSB fallback. A supplied 6000 × 6000 Blender file with 88 channels was converted to a roughly 1.03 GB PSD with 45 layers including seven named Cryptomatte masks (six object masks and one material mask). Every Image RGBA pixel was checked against the source after unpremultiplication, and every pixel of one object mask was independently decoded and compared. The sample artwork is not distributed.

The portable build has a smoke test covering its bundled OpenEXR reader, PSD writer and Tk interface. Photoshop 2026 (27.10) successfully opened the full-size sample with all 45 layers, 32-bit depth and the embedded linear profile. Small PSD and PSB fixtures were opened and saved in Photoshop, then read back to check HDR values, negative values, alpha and mask coverage. Visual equivalence to every EXR-IO option is not claimed.

## Run from source / command line

Python 3.10 or newer, 64-bit:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m blender_batch_exr
```

```powershell
.\.venv\Scripts\python.exe -m blender_batch_exr "D:\Renders" -o "D:\PSDs"
.\.venv\Scripts\python.exe -m blender_batch_exr "D:\Renders" --recursive --format psb
.\.venv\Scripts\python.exe -m blender_batch_exr "image.exr" --no-masks --keep-premultiplied
```

A shared output folder uses source basenames; duplicate basenames are skipped rather than overwritten. The CLI returns a nonzero exit status if a file fails or is skipped because its output exists.

## Build and test

Run `Build.ps1` in PowerShell. The build installs development dependencies, runs tests, and produces `dist/BlenderBatchEXR.exe`. Use a standard Python distribution with working Tcl/Tk support.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe package_release.py
```

Source code: MIT license. Bundled third-party components retain their respective licenses, included in the release archive.
