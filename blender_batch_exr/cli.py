"""GUI dispatch and a shared headless command-line interface."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import sys

from . import __version__
from .converter import convert


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if not argv:
        from .gui import run
        run()
        return 0
    parser = argparse.ArgumentParser(description='Convert Blender EXRs to layered 32-bit PSD/PSB without Photoshop.')
    parser.add_argument('inputs', nargs='*', type=Path, help='EXR files or folders')
    parser.add_argument('--headless', action='store_true', help='Never open the graphical interface')
    parser.add_argument('--version', action='version', version='Blender Batch EXR ' + __version__)
    parser.add_argument('-o', '--output', type=Path, help='Output folder; defaults to beside each EXR')
    parser.add_argument('--format', choices=['auto', 'psd', 'psb'], default='auto')
    parser.add_argument('--no-masks', action='store_true')
    parser.add_argument('--keep-premultiplied', action='store_true')
    parser.add_argument('--recursive', action='store_true', help='Search subfolders')
    parser.add_argument('--log', type=Path, help='Append progress and errors to a UTF-8 log file')
    parser.add_argument('--quiet', action='store_true', help='Suppress console progress; errors and file logging remain')
    parser.add_argument('--skip-existing', action='store_true', help='Treat existing outputs as successful skips')
    args = parser.parse_args(argv)
    if not args.inputs:
        parser.error('provide at least one EXR file or folder')
    with ExitStack() as stack:
        log_file = None
        if args.log:
            try:
                args.log.parent.mkdir(parents=True, exist_ok=True)
                log_file = stack.enter_context(args.log.open('a', encoding='utf-8'))
            except OSError as error:
                parser.error(f'cannot open log file: {error}')

        def report(message, error=False):
            stream = sys.stderr if error else sys.stdout
            if stream is not None and (error or not args.quiet):
                print(message, file=stream, flush=True)
            if log_file:
                print(message, file=log_file, flush=True)

        saved = skipped = failed = 0
        paths = []
        report('Blender Batch EXR ' + __version__ + ' - headless batch started')
        try:
            for p in args.inputs:
                try:
                    if p.is_dir():
                        found = sorted(x for x in (p.rglob('*') if args.recursive else p.iterdir())
                                       if x.is_file() and x.suffix.lower() == '.exr')
                        if not found:
                            raise ValueError('No EXR files found in ' + str(p))
                        paths.extend(found)
                    elif p.is_file() and p.suffix.lower() == '.exr':
                        paths.append(p)
                    else:
                        raise ValueError('Input is not an existing EXR file or folder: ' + str(p))
                except (OSError, ValueError) as error:
                    failed += 1
                    report('ERROR: ' + str(error), error=True)
            paths = list(dict.fromkeys(p.resolve() for p in paths))
            for i, path in enumerate(paths, 1):
                report(f'[{i}/{len(paths)}] {path}')
                try:
                    convert(path, args.output, masks=not args.no_masks,
                            unpremultiply=not args.keep_premultiplied, format=args.format, log=report)
                    saved += 1
                except FileExistsError as error:
                    skipped += 1
                    if not args.skip_existing:
                        failed += 1
                    report('SKIPPED: ' + str(error), error=not args.skip_existing)
                except Exception as error:
                    failed += 1
                    report(f'ERROR {path.name}: {error}', error=True)
        except KeyboardInterrupt:
            report('Cancelled by user.', error=True)
            return 130
        report(f'Finished: {saved} saved, {skipped} skipped, {failed} errors')
        return 1 if failed else 0
