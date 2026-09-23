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
from scanner.installation import compare_installation, locations
from scanner.storage import output_root


def main():
    parser = argparse.ArgumentParser(description='Periksa runtime, paket backend dan popup Desktop tanpa mengubah file')
    parser.add_argument('--compare-installed', action='store_true')
    parser.add_argument('--plugin-dir', type=Path, help='Folder paket backend pada profil yang dipakai')
    parser.add_argument('--hermes-home', type=Path, help='Home/profil backend; default HERMES_HOME atau ~/.hermes')
    parser.add_argument('--desktop-home', type=Path, help='Home aplikasi Desktop, bukan home profil backend')
    parser.add_argument('--desktop-plugin-dir', type=Path, help='Override folder popup yang ditampilkan Capabilities > Plugins')
    args = parser.parse_args()
    result = {'version': __version__, 'python': sys.version.split()[0], 'platform': sys.platform,
              'project_configured': bool(os.environ.get('HERMES_SCANNER_PROJECT')),
              'runtime_root_matches': Path(os.environ.get('HERMES_SCANNER_PROJECT', str(ROOT))).resolve() == ROOT,
              'modules': {name: importlib.util.find_spec(name) is not None for name in
                          ('openpyxl', 'docx', 'reportlab', 'pypdfium2', 'PIL', 'torch', 'mineru_vl_utils')},
              'run_count': len(list((output_root() / 'reviews').glob('*/manifest.json'))),
              'locks': [p.parent.name for p in (output_root() / 'reviews').glob('*/.lock')],
              'gpu_tested': False, 'hermes_dispatch_tested': False}
    if args.compare_installed or any((args.plugin_dir, args.hermes_home, args.desktop_home, args.desktop_plugin_dir)):
        selected = locations(ROOT, hermes_home=args.hermes_home, desktop_home=args.desktop_home,
                             plugin_dir=args.plugin_dir, desktop_plugin_dir=args.desktop_plugin_dir)
        result['selected_paths'] = {k: str(v) for k, v in selected.items()}
        result['paths_are_configured_candidates_not_live_process_detection'] = True
        result['installation'] = compare_installation(ROOT, selected['backend'], selected['desktop'])
        result['success'] = result['installation']['success'] and result['runtime_root_matches']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('Lihat docs/SESSION_AND_SYNC.md. Setelah sync, restart backend dan Reload desktop plugins; popup harus v0.4.2.')
    if result.get('success') is False:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
