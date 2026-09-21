"""Streaming 32-bit PSD/PSB writer using Adobe's public file format.

Layers use ZIP with prediction. The compatibility composite uses raw
planar floats. Lr32 carries floating-point layer records for Photoshop.
"""
from contextlib import contextmanager
import struct
import zlib

import numpy as np


def pack(fmt, *values):
    return struct.pack('>' + fmt, *values)


def predict_float_rows(rows):
    """32-bit PSD prediction: byte planes per row, then byte deltas."""
    h, w = rows.shape
    raw = rows.astype('>f4').view(np.uint8).reshape(h, w, 4)
    shuffled = raw.transpose(0, 2, 1).reshape(h, w * 4).copy()
    shuffled[:, 1:] = shuffled[:, 1:] - shuffled[:, :-1]
    return shuffled.tobytes()


@contextmanager
def section(f, fmt='I', alignment=1):
    pos = f.tell()
    f.write(pack(fmt, 0))
    start = f.tell()
    yield
    size = f.tell() - start
    padding = (-size) % alignment
    f.write(b'\0' * padding)
    end = f.tell()
    f.seek(pos)
    f.write(pack(fmt, size + padding))
    f.seek(end)


def linear_profile(chromaticities=None):
    """ICC v2 matrix profile, linear TRC, Bradford-adapted to D50."""
    c = np.array(chromaticities if chromaticities is not None else
                 ((.64, .33), (.30, .60), (.15, .06), (.3127, .3290))).reshape(4, 2)
    xyz = np.array([[x / y, 1., (1 - x - y) / y] for x, y in c]).T
    matrix = xyz[:, :3] @ np.diag(np.linalg.solve(xyz[:, :3], xyz[:, 3]))
    bradford = np.array([[.8951, .2664, -.1614], [-.7502, 1.7135, .0367], [.0389, -.0685, 1.0296]])
    d50 = np.array([.9642, 1., .8249])
    adaptation = np.linalg.inv(bradford) @ np.diag((bradford @ d50) / (bradford @ xyz[:, 3])) @ bradford
    matrix = adaptation @ matrix

    def xyz_tag(v):
        return b'XYZ ' + b'\0' * 4 + pack('3i', *(round(float(x) * 65536) for x in v))

    label = b'EXR scene linear RGB\0'
    description = b'desc' + b'\0' * 4 + pack('I', len(label)) + label + b'\0' * 78
    tags = [(b'desc', description), (b'cprt', b'text' + b'\0' * 4 + b'Public domain\0'),
            (b'wtpt', xyz_tag(d50))]
    for i, name in enumerate((b'rXYZ', b'gXYZ', b'bXYZ')):
        tags.append((name, xyz_tag(matrix[:, i])))
    for name in (b'rTRC', b'gTRC', b'bTRC'):
        tags.append((name, b'curv' + b'\0' * 4 + pack('IH', 1, 256)))
    header = bytearray(128)
    header[8:24] = pack('I', 0x02100000) + b'mntrRGB XYZ '
    header[24:36] = pack('6H', 2026, 1, 1, 0, 0, 0)
    header[36:40] = b'acsp'
    header[68:80] = pack('3i', *(round(x * 65536) for x in d50))
    offset = 128 + 4 + len(tags) * 12
    table, data = bytearray(), bytearray()
    for name, value in tags:
        table.extend(name + pack('II', offset + len(data), len(value)))
        data.extend(value + b'\0' * (-len(value) % 4))
    result = header + pack('I', len(tags)) + table + data
    result[:4] = pack('I', len(result))
    return result


def write_psd(f, width, height, layers, composite, version=1, profile=None,
              progress=lambda message: None, check_cancel=lambda: None):
    size_fmt = 'Q' if version == 2 else 'I'
    if not 0 < len(layers) <= 32767:
        raise ValueError('Photoshop supports at most 32767 layers.')
    f.write(b'8BPS' + pack('H', version) + b'\0' * 6 + pack('HIIHH', 4, height, width, 32, 3))
    # Photoshop requires HDR toning/view settings in the colour-mode section
    # for 32-bit RGB. An empty section parses in generic readers but Photoshop
    # rejects it with "open options are incorrect". Neutral Linear defaults,
    # verified against a Photoshop 27.10 generated 32-bit document.
    hdr_settings = bytes.fromhex(
        '68647274000000033e6b851f0000000200000007004c0069006e006500610072'
        '0000000200020000000000ff00ff010100000000000000004180000000000001'
        '000000003f80000068647261000000060000000041a0000041f0000000000000'
        '000000003f800000000000000000')
    f.write(pack('I', len(hdr_settings)) + hdr_settings)
    with section(f):
        icc = profile or linear_profile()
        f.write(b'8BIM' + pack('H', 1039) + b'\0\0' + pack('I', len(icc)) + icc)
        f.write(b'\0' * (len(icc) % 2))
    with section(f, size_fmt):
        f.write(pack(size_fmt, 0))  # regular layer info; 32-bit uses Lr32
        f.write(pack('I', 0))  # global mask
        f.write(b'8BIMLr32')
        with section(f, size_fmt, 4):
            f.write(pack('h', -len(layers)))  # merged alpha = transparency
            patches = []
            # Photoshop stores bottom layer first.
            for layer in layers:
                check_cancel()
                h, w = layer.shape
                ids = (-1, 0, 1, 2, 3) if layer.extra_alpha else (-1, 0, 1, 2)
                f.write(pack('4iH', layer.top, layer.left, layer.top + h, layer.left + w, len(ids)))
                positions = []
                for channel in ids:
                    f.write(pack('h', channel))
                    positions.append(f.tell())
                    f.write(pack(size_fmt, 0))
                patches.append(list(zip(ids, positions)))
                f.write(b'8BIMnorm' + bytes((255, 0, 0 if layer.visible else 2, 0)))
                with section(f):
                    f.write(b'\0' * 8)
                    name = layer.name.encode('ascii', 'replace')[:255]
                    pascal = bytes((len(name),)) + name
                    f.write(pascal + b'\0' * (-len(pascal) % 4))
                    unicode_name = layer.name.encode('utf-16-be')
                    value = pack('I', len(unicode_name) // 2) + unicode_name
                    f.write(b'8BIMluni' + pack('I', len(value)) + value)
                    f.write(b'\0' * (-len(value) % 2))
            for layer, positions in zip(layers, patches):
                progress('Writing ' + layer.name)
                for channel, position in positions:
                    check_cancel()
                    start = f.tell()
                    f.write(pack('H', 3))
                    compressor = zlib.compressobj(level=1)
                    plane = layer.plane(3 if channel == -1 else channel)
                    for row in range(0, plane.shape[0], 64):
                        check_cancel()
                        f.write(compressor.compress(predict_float_rows(plane[row:row + 64])))
                    f.write(compressor.flush())
                    end = f.tell()
                    f.seek(position)
                    f.write(pack(size_fmt, end - start))
                    f.seek(end)
    f.write(pack('H', 0))
    alpha = composite.plane(3)
    for channel in range(4):
        plane = composite.plane(channel)
        for row in range(0, height, 64):
            check_cancel()
            block = np.full((min(64, height - row), width), 1 if channel < 3 else 0, dtype=np.float32)
            y0, y1 = max(row, composite.top), min(row + len(block), composite.top + plane.shape[0])
            x0, x1 = max(0, composite.left), min(width, composite.left + plane.shape[1])
            if y1 > y0 and x1 > x0:
                pixels = plane[y0-composite.top:y1-composite.top, x0-composite.left:x1-composite.left]
                if channel < 3:
                    a = alpha[y0-composite.top:y1-composite.top, x0-composite.left:x1-composite.left]
                    pixels = pixels * a + (1 - a)  # PSD compatibility composite is matted on white.
                block[y0-row:y1-row, x0:x1] = pixels
            f.write(block.astype('>f4').tobytes())
