$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE) { throw 'Dependency install failed' }
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE) { throw 'Tests failed' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name BlenderBatchEXR launcher.py
if ($LASTEXITCODE) { throw 'Build failed' }
