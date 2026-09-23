"""Batch conversion using the watcher's Photoshop-free RLAYER4 finishing."""
from pathlib import Path
from tempfile import TemporaryDirectory

from .converter import Cancelled, convert as convert_raw


def convert(source, output_dir=None, *, workflow='rlayer4', masks=True,
            unpremultiply=True, format='auto', log=lambda message: None, cancel=None):
    if workflow not in ('rlayer4', 'raw'):
        raise ValueError('Workflow must be rlayer4 or raw.')
    options = dict(masks=masks, unpremultiply=unpremultiply, format=format,
                   log=log, cancel=cancel)
    if workflow == 'raw':
        return convert_raw(source, output_dir, **options)

    from .headless_rlayer4 import finish
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve() if output_dir else source.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    # Reserve the basename across both formats for predictable batch retries.
    for suffix in ('.psd', '.psb'):
        destination = output_dir / (source.stem + suffix)
        if destination.exists():
            raise FileExistsError('Already exists (not overwritten): ' + str(destination))
    if cancel is not None and cancel.is_set():
        raise Cancelled('Cancelled')
    # The raw HDR document is private staging, never an apparently finished output.
    with TemporaryDirectory(prefix='.rlayer4-', dir=output_dir) as staging:
        raw = convert_raw(source, staging, **options)
        destination = output_dir / raw.name
        log('Applying Photoshop-free RLAYER4 finishing')
        return finish(raw, destination, log=log, cancel=cancel)
