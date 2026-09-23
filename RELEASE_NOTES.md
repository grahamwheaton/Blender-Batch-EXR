# 0.3.0 — batch RLAYER4 finishing

- Default GUI and CLI pipeline uses the watcher's Photoshop-free RLAYER4 finishing.
- Produces 8-bit sRGB COMP/RLAYERS groups, blend settings and editable masks.
- Raw 32-bit HDR mode remains available via the checkbox or --workflow raw.
- Private intermediates, cancellation before publication and existing-output protection.
- Requires Diff/Image passes and standard scene-linear sRGB inputs for finishing.
## v0.2.0 — Match EXR-IO layer layout

- Remove raw Cryptomatte data layers when generating decoded masks.
- Match `.RGBA` pass names, dot-separated mask names, layer order and visibility.
- Generate white masks with transparent coverage instead of opaque grayscale layers.
- Crop transparent margins and retain empty passes.
- Match EXR-IO's near-zero-alpha unpremultiplication and extra alpha channels.

Compared against a supplied EXR-IO reference: **all 13 layers match in names, order, visibility, blend mode, opacity, bounds and every stored layer-channel pixel**. The sample includes six object masks and one material mask.

Extract the ZIP and run **BlenderBatchEXR.exe**. The window title shows **0.2.0**. Use a new output folder when reconverting; existing files are never overwritten.

Windows x64, portable; no Photoshop, Blender, EXR-IO or Python installation required. Output remains 32-bit scene-linear RGB; Blender's AgX/Filmic look is not baked in. See README for limitations.
