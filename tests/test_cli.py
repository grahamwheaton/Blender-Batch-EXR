from pathlib import Path
import subprocess
import sys

import numpy as np
import OpenEXR
from psd_tools import PSDImage

ROOT = Path(__file__).resolve().parents[1]


def exr(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    OpenEXR.File({}, {c: np.ones((2, 3), np.float32) for c in 'RGBA'}).write(str(path))


def cli(*args, launcher='cli_launcher.py'):
    return subprocess.run([sys.executable, str(ROOT / launcher), '--workflow', 'raw', *map(str, args)],
                          cwd=ROOT, capture_output=True, encoding='utf-8', timeout=30)


def test_headless_files_recursive_log_and_exit(tmp_path):
    src = tmp_path / 'input space'
    exr(src / 'one.exr')
    exr(src / 'nested' / 'two.EXR')
    output = tmp_path / 'output'
    log = tmp_path / 'logs' / 'batch.log'
    result = cli(src, '--recursive', '-o', output, '--log', log, '--format', 'psb')
    assert result.returncode == 0, result.stderr
    assert len(list(output.glob('*.psb'))) == 2
    assert PSDImage.open(output / 'one.psb').depth == 32
    assert '2 saved' in result.stdout and '2 saved' in log.read_text(encoding='utf-8')
    assert cli(src, '--recursive', '-o', output, '--format', 'psb').returncode == 1
    result = cli(src, '--recursive', '-o', output, '--format', 'psb', '--skip-existing', '--quiet', '--log', log)
    assert result.returncode == 0 and result.stdout == ''
    assert '2 skipped' in log.read_text(encoding='utf-8')


def test_dispatch_and_failures(tmp_path):
    src = tmp_path / 'one.exr'
    exr(src)
    assert cli('--headless', src, '-o', tmp_path / 'gui-route', launcher='launcher.py').returncode == 0
    assert cli().returncode == 2
    assert cli('--headless', launcher='launcher.py').returncode == 2
    assert cli('--help').returncode == 0
    result = cli(tmp_path / 'missing.exr', src, '-o', tmp_path / 'continued')
    assert result.returncode == 1 and (tmp_path / 'continued' / 'one.psd').exists()


def test_headless_does_not_import_gui(tmp_path):
    src = tmp_path / 'one.exr'
    exr(src)
    code = ('import sys; from blender_batch_exr.cli import main; '
            'status=main(sys.argv[1:]); '
            'assert "tkinter" not in sys.modules; '
            'assert "blender_batch_exr.gui" not in sys.modules; raise SystemExit(status)')
    result = subprocess.run([sys.executable, '-c', code, '--headless', '--workflow', 'raw', str(src)],
                            cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_headless_default_rlayer4(tmp_path):
    src = tmp_path / 'render.exr'
    OpenEXR.File({}, {f'{p}.{c}': np.ones((2, 3), np.float32)
                     for p in ('Diff', 'Image') for c in 'RGBA'}).write(str(src))
    result = subprocess.run([sys.executable, str(ROOT / 'cli_launcher.py'), str(src)],
                            cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    doc = PSDImage.open(src.with_suffix('.psd'))
    assert doc.depth == 8 and {x.name for x in doc} == {'COMP', 'RLAYERS'}
