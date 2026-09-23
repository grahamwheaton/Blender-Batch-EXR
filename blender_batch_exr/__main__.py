import argparse
from pathlib import Path
import sys

from .workflow import convert


def main():
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    if len(sys.argv) == 1:
        from .gui import run
        run()
        return
    parser = argparse.ArgumentParser(description='Batch EXR to RLAYER4 layered PSD/PSB without Photoshop.')
    parser.add_argument('inputs', nargs='+', type=Path, help='EXR files or folders')
    parser.add_argument('-o', '--output', type=Path)
    parser.add_argument('--format', choices=['auto', 'psd', 'psb'], default='auto')
    parser.add_argument('--no-masks', action='store_true')
    parser.add_argument('--keep-premultiplied', action='store_true')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--workflow', choices=['rlayer4', 'raw'], default='rlayer4',
                        help='RLAYER4 8-bit finishing (default), or raw 32-bit HDR')
    args = parser.parse_args()
    paths = []
    for p in args.inputs:
        paths.extend(sorted(p.rglob('*.exr') if args.recursive else p.glob('*.exr')) if p.is_dir() else [p])
    paths = list(dict.fromkeys(p.resolve() for p in paths))
    failed = not paths
    if not paths:
        print('No EXR files found.', file=sys.stderr)
    for path in paths:
        try:
            convert(path, args.output, masks=not args.no_masks,
                    unpremultiply=not args.keep_premultiplied, format=args.format,
                    workflow=args.workflow, log=print)
        except Exception as error:
            failed = True
            print(f'ERROR {path.name}: {error}', file=sys.stderr)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
