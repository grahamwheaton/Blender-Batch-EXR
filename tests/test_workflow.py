import threading

import numpy as np
import OpenEXR
import pytest
from psd_tools import PSDImage

from blender_batch_exr.converter import Cancelled
from blender_batch_exr.workflow import convert


def fixture(path, passes=('Image', 'Diff', 'Gloss', 'AO')):
    OpenEXR.File({}, {name + '.' + channel: np.full((4, 6), value, np.float32)
                     for name in passes
                     for channel, value in [('R', .2), ('G', .4), ('B', .6), ('A', 1)]}).write(str(path))
    return path


@pytest.mark.parametrize('format', ['auto', 'psd', 'psb'])
def test_exr_to_finished_document(tmp_path, format):
    source = fixture(tmp_path / 'render.exr')
    original = source.read_bytes()
    result = convert(source, format=format)
    doc = PSDImage.open(result)
    assert doc.depth == 8 and doc.size == (6, 4)
    assert {layer.name for layer in doc} == {'COMP', 'RLAYERS'}
    assert result.suffix == ('.psb' if format == 'psb' else '.psd')
    assert source.read_bytes() == original
    assert not list(tmp_path.glob('.rlayer4-*'))
    saved = result.read_bytes()
    with pytest.raises(FileExistsError):
        convert(source, format='psb' if format != 'psb' else 'psd')
    assert result.read_bytes() == saved


def test_raw_and_invalid_passes(tmp_path):
    source = fixture(tmp_path / 'beauty.exr', ('Combined',))
    with pytest.raises(ValueError, match='Diff and Image'):
        convert(source)
    assert list(tmp_path.iterdir()) == [source]
    assert PSDImage.open(convert(source, workflow='raw')).depth == 32


@pytest.mark.parametrize('stage', ['Creating 8-bit', 'Finishing Image', 'Compositing finished'])
def test_cancel_finishing_cleans_staging_and_output(tmp_path, stage):
    source = fixture(tmp_path / 'cancel.exr')
    cancel = threading.Event()
    def log(message):
        if message.startswith(stage):
            cancel.set()
    with pytest.raises(Cancelled):
        convert(source, cancel=cancel, log=log)
    assert list(tmp_path.iterdir()) == [source]


def test_publication_race_preserves_existing_output(tmp_path):
    source = fixture(tmp_path / 'race.exr')
    output = tmp_path / 'race.psd'
    def log(message):
        if message.startswith('Compositing finished'):
            output.write_bytes(b'existing document')
    with pytest.raises(FileExistsError):
        convert(source, log=log)
    assert output.read_bytes() == b'existing document'
    assert not list(tmp_path.glob('*.partial'))
    assert not list(tmp_path.glob('.rlayer4-*'))
