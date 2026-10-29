"""DBCI-QC command-line adapter for the public toolkit; no web dependencies."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

from . import __version__
from .toolkit import catalog, inspect_recording, prepare_recording, build_plan, run_modules


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _execution_failed(result):
    if result.get('status') not in {'completed', 'partial'}:
        return True
    for module in result.get('modules', []):
        if module.get('status') == 'failed' or module.get('summary', {}).get('window_status_counts', {}).get('failed', 0):
            return True
    return any(window.get('status') in {'failed', 'cancelled', 'interrupted'} or
               any(module.get('status') == 'failed' for module in window.get('modules', []))
               for window in result.get('windows', []))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='dbci-qc', description='Modular electrophysiology QC without a web server')
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('catalog', help='List modules, methods and dependencies')
    inspect = commands.add_parser('inspect', help='Inspect technical metadata without QC')
    inspect.add_argument('source')
    prepare = commands.add_parser('prepare', help='Freeze source metadata and explicitly confirmed selection')
    prepare.add_argument('source')
    prepare.add_argument('--id', required=True)
    prepare.add_argument('--modality', choices=['scalp_eeg'], required=True)
    prepare.add_argument('--config', required=True, help='QC configuration JSON with explicit EEG indices')
    prepare.add_argument('--reference-scheme', default='unknown')
    prepare.add_argument('--output', required=True, help='New recording JSON file; never overwrite')
    for name in ('plan', 'run'):
        command = commands.add_parser(name, help='Plan or run explicitly selected modules')
        command.add_argument('--record', required=True, help='Reviewed recording JSON from prepare')
        command.add_argument('--modules', required=True, nargs='+', choices=[f'M{i:02d}' for i in range(1, 10)])
        command.add_argument('--config', help='Optional configuration overrides')
        if name == 'run':
            command.add_argument('--output', required=True, help='New output directory')
    args = parser.parse_args(argv)
    try:
        # Reserve stdout for one JSON value, even when scientific backends log.
        with redirect_stdout(sys.stderr):
            if args.command == 'catalog':
                result = catalog()
            elif args.command == 'inspect':
                result = inspect_recording(args.source)
            elif args.command == 'prepare':
                result = prepare_recording(args.source, record_id=args.id, modality=args.modality,
                                           qc_config=_read(args.config), reference_scheme=args.reference_scheme)
                with Path(args.output).open('x', encoding='utf-8') as target:
                    target.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            else:
                record = _read(args.record)
                config = _read(args.config) if args.config else None
                if args.command == 'plan':
                    result = build_plan(record, args.modules, config)
                else:
                    result = run_modules(record, args.output, args.modules, qc_config=config)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        if args.command == 'run' and _execution_failed(result):
            return 1
        return 0
    except (OSError, ValueError, TypeError, KeyError, ImportError) as error:
        print(json.dumps({'error': type(error).__name__, 'message': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
