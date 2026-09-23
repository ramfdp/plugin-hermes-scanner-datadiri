"""Read-only runtime diagnostics. Never prints API keys or full environment variables."""
import importlib.util
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scanner import __version__
from scanner.storage import output_root


def main():
    result = {'version': __version__, 'python': sys.version.split()[0], 'platform': sys.platform,
              'project_configured': bool(os.environ.get('HERMES_SCANNER_PROJECT')),
              'runtime_root_matches': Path(os.environ.get('HERMES_SCANNER_PROJECT', str(ROOT))).resolve() == ROOT,
              'modules': {name: importlib.util.find_spec(name) is not None for name in
                          ('openpyxl', 'docx', 'reportlab', 'pypdfium2', 'PIL', 'torch', 'mineru_vl_utils')},
              'run_count': len(list((output_root() / 'reviews').glob('*/manifest.json'))),
              'locks': [p.parent.name for p in (output_root() / 'reviews').glob('*/.lock')],
              'gpu_tested': False, 'hermes_dispatch_tested': False}
    print(json.dumps(result, indent=2))
    print('Use docs/DEBUGGING.md for logs, individual tests, and stale-state recovery.')


if __name__ == '__main__':
    main()
