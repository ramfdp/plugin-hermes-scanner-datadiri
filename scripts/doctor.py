"""Read-only diagnostics. Never prints API keys or full environment variables."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scanner import __version__
from scanner.installation import compare_installation
from scanner.storage import output_root


def main():
    parser = argparse.ArgumentParser(description='Periksa runtime dan salinan plugin terpasang tanpa mengubah file')
    parser.add_argument('--compare-installed', action='store_true')
    parser.add_argument('--plugin-dir', type=Path, help='Folder plugin terpasang; gunakan untuk profil Hermes nondefault')
    args = parser.parse_args()
    result = {'version': __version__, 'python': sys.version.split()[0], 'platform': sys.platform,
              'project_configured': bool(os.environ.get('HERMES_SCANNER_PROJECT')),
              'runtime_root_matches': Path(os.environ.get('HERMES_SCANNER_PROJECT', str(ROOT))).resolve() == ROOT,
              'modules': {name: importlib.util.find_spec(name) is not None for name in
                          ('openpyxl', 'docx', 'reportlab', 'pypdfium2', 'PIL', 'torch', 'mineru_vl_utils')},
              'run_count': len(list((output_root() / 'reviews').glob('*/manifest.json'))),
              'locks': [p.parent.name for p in (output_root() / 'reviews').glob('*/.lock')],
              'gpu_tested': False, 'hermes_dispatch_tested': False}
    if args.compare_installed or args.plugin_dir:
        home = Path(os.environ.get('HERMES_HOME') or (Path.home() / '.hermes'))
        target = args.plugin_dir or home / 'plugins' / 'hermes-scanner-datadiri'
        result['installation'] = compare_installation(ROOT, target)
        result['success'] = result['installation']['success'] and result['runtime_root_matches']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Lihat docs/WORKFLOW.md untuk alur, sinkronisasi plugin dan batas pengujian.')
    if result.get('success') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
