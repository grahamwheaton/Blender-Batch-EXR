import json
import threading

import numpy as np
import OpenEXR
from PIL import ImageCms
from psd_tools import PSDImage
import pytest

from blender_batch_exr.converter import Cancelled, convert
from blender_batch_exr.psd import linear_profile


def fixture_exr(path, offset=False):
    a = np.array([[1, .5, 0], [1, 1, 1]], np.float32)
    r = np.array([[4, 1, 0], [-.2, .3, .4]], np.float32)
    channels = {'ViewLayer.Combined.R': r, 'ViewLayer.Combined.G': r * .5,
                'ViewLayer.Combined.B': r * .25, 'ViewLayer.Combined.A': a,
                'ViewLayer.Depth.Z': np.full_like(r, 25)}
    hash_id = 0x3f800001
    ids = np.full_like(r, np.array(hash_id, np.uint32).view(np.float32))
    coverage = np.array([[1, .25, 0], [.5, 0, 1]], np.float32)
    channels.update({'CryptoObject00.r': ids, 'CryptoObject00.g': coverage,
                     'CryptoObject00.b': np.zeros_like(r), 'CryptoObject00.a': np.zeros_like(r)})
    header = {'cryptomatte/abc/name': 'CryptoObject',
              'cryptomatte/abc/manifest': json.dumps({'Test object 🎨': f'{hash_id:08x}'})}
    if offset:
        header['displayWindow'] = (np.array([0, 0], np.int32), np.array([4, 3], np.int32))
        header['dataWindow'] = (np.array([1, 1], np.int32), np.array([3, 2], np.int32))
    OpenEXR.File(header, channels).write(str(path))
    return r, a, coverage


@pytest.mark.parametrize('format', ['psd', 'psb'])
def test_roundtrip_layers_hdr_alpha_masks(tmp_path, format):
    source = tmp_path / 'sample.exr'
    r, a, coverage = fixture_exr(source)
    out = convert(source, format=format)
    psd = PSDImage.open(out)
    assert psd.depth == 32
    assert psd._record.color_mode_data.value.startswith(b'hdrt')
    assert psd.size == (3, 2)
    layers = {layer.name: layer for layer in psd}
    beauty = layers['ViewLayer.Combined']
    assert beauty.visible
    assert sum(layer.visible for layer in psd) == 1
    np.testing.assert_allclose(beauty.numpy()[..., 0], [[4, 2, 0], [-.2, .3, .4]])
    np.testing.assert_allclose(beauty.numpy()[..., 3], a)
    np.testing.assert_allclose(layers['ViewLayer.Depth.Z'].numpy()[..., 0], 25)
    np.testing.assert_allclose(layers['CryptoObject / Test object 🎨'].numpy()[..., 0], coverage)
    np.testing.assert_allclose(psd.numpy()[..., 0][a > 0], beauty.numpy()[..., 0][a > 0], atol=1e-6)
    np.testing.assert_allclose(psd.numpy()[..., 3], a)
    assert out.suffix == '.' + format


def test_offset_and_no_masks(tmp_path):
    source = tmp_path / 'crop.exr'
    fixture_exr(source, offset=True)
    out = convert(source, masks=False, unpremultiply=False)
    psd = PSDImage.open(out)
    assert psd.size == (5, 4)
    assert not any(' / ' in layer.name for layer in psd)
    assert psd[-1].offset == (1, 1)
    np.testing.assert_allclose(psd.numpy()[1:3, 1:4, 0][psd.numpy()[1:3, 1:4, 3] > 0], np.array([[4, 1, 0], [-.2, .3, .4]])[psd.numpy()[1:3, 1:4, 3] > 0], atol=1e-6)
    assert np.count_nonzero(psd.numpy()[0, :, 3]) == 0


def test_existing_output_and_cancellation(tmp_path):
    source = tmp_path / 'sample.exr'
    fixture_exr(source)
    out = convert(source)
    original = out.read_bytes()
    with pytest.raises(FileExistsError):
        convert(source)
    assert out.read_bytes() == original
    event = threading.Event()
    event.set()
    with pytest.raises(Cancelled):
        convert(source, cancel=event)
    assert not list(tmp_path.glob('*.partial'))


def test_cancel_during_write(tmp_path):
    source = tmp_path / 'cancel.exr'
    fixture_exr(source)
    event = threading.Event()
    def log(s):
        if s.startswith('Writing'):
            event.set()
    with pytest.raises(Cancelled):
        convert(source, log=log, cancel=event)
    assert not (tmp_path / 'cancel.psd').exists()
    assert not list(tmp_path.glob('*.partial'))


def test_icc():
    import io
    profile = ImageCms.ImageCmsProfile(io.BytesIO(linear_profile()))
    assert 'EXR scene linear RGB' in ImageCms.getProfileDescription(profile)


def test_auto_fallback(tmp_path, monkeypatch):
    import blender_batch_exr.converter as module
    source = tmp_path / 'large.exr'
    fixture_exr(source)
    monkeypatch.setattr(module, 'PSD_LIMIT', 1_000_001)
    out = convert(source)
    assert out.suffix == '.psb'
    assert PSDImage.open(out).depth == 32
    assert not (tmp_path / 'large.psd').exists()
    assert not list(tmp_path.glob('*.partial'))


def test_missing_manifest_fails_without_partial(tmp_path):
    source = tmp_path / 'broken.exr'
    OpenEXR.File({'cryptomatte/abc/name': 'CryptoObject'}, {'R': np.zeros((2, 2), np.float32)}).write(str(source))
    with pytest.raises(ValueError, match='Missing Cryptomatte manifest'):
        convert(source)
    assert not list(tmp_path.glob('*.psd'))
