"""Package the portable executable with documentation and dependency licenses."""
from importlib.metadata import distribution
from pathlib import Path
import sys
import zipfile


root = Path(__file__).resolve().parent
output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'dist'
archive = output_dir / 'BlenderBatchEXR-Windows-x64.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(output_dir / 'BlenderBatchEXR.exe', 'BlenderBatchEXR.exe')
    z.write(output_dir / 'BlenderBatchEXR-CLI.exe', 'BlenderBatchEXR-CLI.exe')
    for name in ['README.md', 'README-HEADLESS.md', 'LICENSE', 'RELEASE_NOTES.md']:
        z.write(root / name, name)
    for package in ['OpenEXR', 'numpy', 'pyinstaller']:
        dist = distribution(package)
        for item in dist.files or []:
            if 'license' in str(item).lower() or 'copying' in str(item).lower():
                path = Path(dist.locate_file(item))
                if path.is_file():
                    z.write(path, 'licenses/' + package + '/' + str(item).replace('..', '_'))
    base = Path(sys.base_prefix)
    z.write(base / 'LICENSE.txt', 'licenses/Python-LICENSE.txt')
    for sub in ['tcl8.6', 'tk8.6']:
        path = base / 'tcl' / sub / 'license.terms'
        if path.exists():
            z.write(path, 'licenses/' + sub + '-license.terms')
        else:
            # Standard Windows Python includes Tcl/Tk terms in LICENSE.txt.
            license_text = (base / 'LICENSE.txt').read_text(encoding='utf-8')
            if 'Sun Microsystems' not in license_text or 'Tcl' not in license_text:
                raise FileNotFoundError('Tcl/Tk license missing from Python distribution.')
print(archive)
