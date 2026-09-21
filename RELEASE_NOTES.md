Standalone Windows x64 preview of Blender Batch EXR.

- Batch conversion to layered 32-bit PSD, with automatic PSB fallback.
- Named Cryptomatte object/material masks with fractional edge coverage.
- HDR values, pass transparency, Unicode layer names and cropped windows.
- Portable EXE: no Photoshop, Blender, EXR-IO or Python installation required.
- Original EXRs remain unchanged; existing outputs are skipped.

Extract the ZIP and run **BlenderBatchEXR.exe**. Add EXRs, choose an output folder and click **Convert batch**.

Validated with automated independent-reader tests and a 6000 × 6000 / 88-channel Blender EXR. Photoshop 2026 (27.10) successfully opened its 45-layer 32-bit PSD; small PSD/PSB fixtures were also checked. Colour stays scene-linear; Blender's AgX/Filmic look is not baked in. Large multilayer EXRs require substantial RAM. See README for supported formats and limits.
