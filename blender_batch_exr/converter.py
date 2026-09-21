from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import tempfile

import numpy as np
import OpenEXR

from .psd import linear_profile, write_psd


class Cancelled(Exception):
    pass


class PSDTooLarge(Exception):
    pass


PSD_LIMIT = 2_000_000_000


@dataclass(eq=False)
class Layer:
    name: str
    rgb: tuple
    alpha: object
    top: int
    left: int
    shape: tuple
    visible: bool = False
    unpremultiply: bool = False
    extra_alpha: bool = False

    def plane(self, index):
        if index == 3:
            return np.ones(self.shape, np.float32) if self.alpha is None else np.asarray(self.alpha, np.float32)
        value = self.rgb[index]
        result = np.asarray(value() if callable(value) else value, np.float32)
        if self.unpremultiply and self.alpha is not None:
            # EXR-IO limits amplification around zero-alpha antialiased edges.
            result = result / np.maximum(self.alpha, np.float32(1 / 32768))
        return result


def crop_layer(layer):
    """Trim transparent margins like EXR-IO/Photoshop, keeping empty layers."""
    if layer.alpha is None:
        return layer
    occupied = layer.alpha != 0
    ys = np.flatnonzero(np.any(occupied, axis=1))
    xs = np.flatnonzero(np.any(occupied, axis=0))
    if not len(ys) or not len(xs):
        layer.top = layer.left = 0
        bounds = np.s_[:0, :0]
    else:
        bounds = np.s_[ys[0]:ys[-1]+1, xs[0]:xs[-1]+1]
        layer.top += int(ys[0])
        layer.left += int(xs[0])
    layer.rgb = tuple(v[bounds] for v in layer.rgb)
    layer.alpha = layer.alpha[bounds]
    layer.shape = layer.alpha.shape
    return layer


def crypto_layers(part, source, top, left, shape, log, check):
    header = part.header
    result = []
    for key in sorted(header, key=lambda k: str(header[k]) if k.endswith('/name') else k):
        if not key.startswith('cryptomatte/') or not key.endswith('/name'):
            continue
        check()
        prefix = key.rsplit('/', 1)[0]
        stream = header[key]
        if header.get(prefix + '/conversion', 'uint32_to_float32') != 'uint32_to_float32':
            raise ValueError('Unsupported Cryptomatte ID conversion: ' + stream)
        manifest = header.get(prefix + '/manifest')
        if manifest is None and prefix + '/manif_file' in header:
            sidecar = (source.parent / header[prefix + '/manif_file']).resolve()
            if not sidecar.is_relative_to(source.parent.resolve()):
                raise ValueError('Cryptomatte sidecar must be inside the EXR folder.')
            manifest = sidecar.read_text(encoding='utf-8')
        if manifest is None:
            raise ValueError('Missing Cryptomatte manifest for ' + stream)
        manifest = json.loads(manifest)
        initial_count = len(result)
        pairs = []
        names = sorted({n.rsplit('.', 1)[0] for n in part.channels
                        if re.fullmatch(re.escape(stream) + r'\d+\.[RGBArgba]', n)})
        for name in names:
            channels = {n.rsplit('.', 1)[-1].upper(): c.pixels for n, c in part.channels.items()
                        if n.rsplit('.', 1)[0] == name}
            for id_name, coverage_name in [('R', 'G'), ('B', 'A')]:
                if id_name not in channels or coverage_name not in channels:
                    raise ValueError('Incomplete Cryptomatte channel pair in ' + name)
                ids = np.ascontiguousarray(channels[id_name], dtype=np.float32).view(np.uint32)
                pairs.append((ids, channels[coverage_name]))
        if not pairs:
            raise ValueError('Cryptomatte manifest has no matching channels: ' + stream)
        present = set()
        for ids, coverage in pairs:
            check()
            present.update(int(v) for v in np.unique(ids[coverage > 0]))
        def float_id(item):
            bits = int(item[1], 16)
            if (bits >> 23) & 255 in (0, 255):
                bits ^= 1 << 23
            return np.array(bits, np.uint32).view(np.float32).item()

        for name, hex_id in sorted(manifest.items(), key=float_id):
            check()
            hash_id = int(hex_id, 16)
            exponent = (hash_id >> 23) & 255
            if exponent in (0, 255):
                hash_id ^= 1 << 23
            if hash_id not in present:
                continue

            value = np.zeros(shape, np.float32)
            for ids, coverage in pairs:
                check()
                np.add(value, np.where(ids == hash_id, coverage, 0), out=value)
            np.clip(value, 0, 1, out=value)
            # EXR-IO masks are white silhouettes with coverage in transparency,
            # not opaque black/white images.
            white = (value > 0).astype(np.float32)
            layer = crop_layer(Layer(stream + '.' + name, (white,) * 3, value,
                                     top, left, shape, visible=True, extra_alpha=True))
            # Own the cropped mask arrays so the full-frame backing can be freed.
            layer.alpha = layer.alpha.copy()
            white = layer.rgb[0].copy()
            layer.rgb = (white,) * 3
            result.append(layer)
        log(f'{stream}: {len(result) - initial_count} mask layers')
    return result


def collect_layers(exr, source, masks, unpremultiply, log, check):
    display = exr.parts[0].header['displayWindow']
    width, height = (int(v) for v in (display[1] - display[0] + 1))
    layers = []
    mask_layers = []
    for index, part in enumerate(exr.parts):
        check()
        if part.header['type'] in (OpenEXR.deepscanline, OpenEXR.deeptile):
            raise ValueError('Deep EXR is unsupported. Export a regular multilayer EXR from Blender.')
        if not np.array_equal(part.header['displayWindow'], display):
            raise ValueError('EXR parts have different display windows.')
        if not np.array_equal(part.header.get('chromaticities'), exr.parts[0].header.get('chromaticities')):
            raise ValueError('EXR parts have different colour primaries.')
        start = part.header['dataWindow'][0] - display[0]
        left, top = (int(v) for v in start)
        groups = {}
        crypto_streams = [v for k, v in part.header.items() if k.startswith('cryptomatte/') and k.endswith('/name')]
        for name, channel in part.channels.items():
            if channel.xSampling != 1 or channel.ySampling != 1:
                raise ValueError('Subsampled EXR channels are unsupported: ' + name)
            if channel.pixels.dtype == np.uint32:
                raise ValueError('Integer EXR channel cannot be stored losslessly in float PSD: ' + name)
            group, _, component = name.rpartition('.')
            groups.setdefault(group, {})[component] = channel.pixels
        for group, channels in sorted(groups.items()):
            raw_crypto = any(re.fullmatch(re.escape(stream) + r'\d+', group) for stream in crypto_streams)
            if masks and raw_crypto:
                continue
            shape = next(iter(channels.values())).shape
            name = group or part.header.get('name') or 'Image'
            if len(exr.parts) > 1:
                name = str(part.header.get('name', f'Part {index + 1}')) + ' / ' + name
            used = set()
            for components in [('R', 'G', 'B'), ('r', 'g', 'b'), ('X', 'Y', 'Z'), ('x', 'y', 'z')]:
                if all(c in channels for c in components):
                    alpha_key = 'a' if components[0].islower() else 'A'
                    alpha = channels.get(alpha_key) if components[0].upper() == 'R' else None
                    # Cryptomatte A is coverage for the B ID, never transparency.
                    if raw_crypto:
                        alpha = None
                    suffix = ''.join(components) + (alpha_key if alpha is not None else '')
                    layers.append(crop_layer(Layer(name + '.' + suffix, tuple(channels[c] for c in components), alpha,
                                        top, left, shape, visible=True, extra_alpha=alpha is not None,
                                        unpremultiply=unpremultiply and not raw_crypto and components[0].upper() == 'R')))
                    used.update(components)
                    if alpha is not None:
                        used.add(alpha_key)
                    break
            for component, pixels in sorted(channels.items()):
                if component not in used:
                    layers.append(Layer(name + '.' + component, (pixels,) * 3, None, top, left, shape, visible=True))
        if masks:
            mask_layers.extend(crypto_layers(part, source, top, left, shape, log, check))
    layers = mask_layers + sorted(layers, key=lambda layer: layer.name, reverse=True)
    if not layers:
        raise ValueError('EXR contains no supported image channels.')
    # All EXR-IO imported layers are visible; composite the actual stack.
    combined = composite_layers(layers, width, height, check)
    return width, height, layers, combined


def composite_layers(layers, width, height, check):
    top = layers[-1]
    if top.left == 0 and top.top == 0 and top.shape == (height, width) and (top.alpha is None or np.all(top.alpha == 1)):
        return top
    alpha = np.zeros((height, width), np.float32)
    rgb = tuple(np.zeros_like(alpha) for _ in range(3))
    for layer in layers:
        check()
        if not layer.visible:
            continue
        h, w = layer.shape
        x0, y0 = max(0, layer.left), max(0, layer.top)
        x1, y1 = min(width, layer.left + w), min(height, layer.top + h)
        if x1 <= x0 or y1 <= y0:
            continue
        src = np.s_[y0-layer.top:y1-layer.top, x0-layer.left:x1-layer.left]
        dst = np.s_[y0:y1, x0:x1]
        a = layer.plane(3)[src]
        for i in range(3):
            rgb[i][dst] = layer.plane(i)[src] * a + rgb[i][dst] * (1 - a)
        alpha[dst] = a + alpha[dst] * (1 - a)
    for v in rgb:
        np.divide(v, alpha, out=v, where=alpha != 0)
    return Layer('Composite', rgb, alpha, 0, 0, (height, width))


def convert(source, output_dir=None, *, masks=True, unpremultiply=True, format='auto',
            log=lambda message: None, cancel=None):
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve() if output_dir else source.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    def check():
        if cancel is not None and cancel.is_set():
            raise Cancelled('Cancelled')

    check()
    log('Reading ' + source.name)
    # Read one EXR at a time; no Photoshop process is involved.
    with OpenEXR.File(str(source), separate_channels=True) as exr:
        check()
        width, height, layers, combined = collect_layers(exr, source, masks, unpremultiply, log, check)
        if max(width, height) > 300000 or min(width, height) < 1:
            raise ValueError('Image dimensions exceed Photoshop limits.')
        large = max(width, height) > 30000
        if format not in ('auto', 'psd', 'psb'):
            raise ValueError('Format must be auto, psd or psb.')
        if format == 'psd' and large:
            raise ValueError('This file may exceed PSD limits. Select Auto or PSB.')
        version = 2 if format == 'psb' or (format == 'auto' and large) else 1
        suffix = '.psb' if version == 2 else '.psd'
        destination = output_dir / (source.stem + suffix)
        if destination.exists():
            raise FileExistsError('Already exists (not overwritten): ' + str(destination))
        log(f'{width} × {height}, {len(layers)} layers → {destination.name}')
        profile = linear_profile(exr.parts[0].header.get('chromaticities'))
        fd, temporary = tempfile.mkstemp(prefix=destination.name + '.', suffix='.partial', dir=output_dir)
        try:
            with os.fdopen(fd, 'w+b') as f:
                def write_check():
                    check()
                    if version == 1 and f.tell() > PSD_LIMIT - 1_000_000:
                        raise PSDTooLarge('Output exceeds PSD size limit. Select Auto or PSB.')
                try:
                    write_psd(f, width, height, layers, combined, version, profile, log, write_check)
                    write_check()
                except PSDTooLarge:
                    if format != 'auto':
                        raise
                    version = 2
                    destination = output_dir / (source.stem + '.psb')
                    if destination.exists():
                        raise FileExistsError('Already exists (not overwritten): ' + str(destination))
                    log('PSD limit reached; rewriting as PSB: ' + destination.name)
                    f.seek(0)
                    f.truncate()
                    write_psd(f, width, height, layers, combined, version, profile, log, check)
                f.flush()
                os.fsync(f.fileno())
            check()
            # Atomic publication without overwriting an existing file.
            if os.name == 'nt':
                os.rename(temporary, destination)
            else:
                os.link(temporary, destination)
                os.unlink(temporary)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    log('Saved ' + str(destination))
    return destination
