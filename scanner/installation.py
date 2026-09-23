"""Read-only comparison of runtime, backend package and app-level Desktop copy."""
import hashlib
import json
import os
import re
from pathlib import Path

PLUGIN_ID = 'hermes-scanner-datadiri'
MARKER = '.hermes-package.json'
LEGACY = ('tools.py', 'schemas.py', 'ocr_runner.py', 'exporter.py', 'cv_report.py')


def _digest(path):
    # Compare code, not newline conventions from a Windows checkout.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def locations(runtime_root, *, hermes_home=None, desktop_home=None, plugin_dir=None, desktop_plugin_dir=None):
    runtime = Path(runtime_root).expanduser().absolute()
    home = Path(hermes_home or os.environ.get('HERMES_HOME') or Path.home() / '.hermes').expanduser().absolute()
    # Hermes Desktop is app-level even when the backend uses profiles/<name>.
    app_home = Path(desktop_home).expanduser().absolute() if desktop_home else (home.parent.parent if home.parent.name == 'profiles' else home)
    return {'runtime': runtime, 'hermes_home': home, 'desktop_home': app_home,
            'backend': Path(plugin_dir).expanduser().absolute() if plugin_dir else home / 'plugins' / PLUGIN_ID,
            'desktop': Path(desktop_plugin_dir).expanduser().absolute() if desktop_plugin_dir else app_home / 'desktop-plugins' / PLUGIN_ID}


def _version(path):
    if not path.is_file():
        return None
    match = re.search(r"(?:const VERSION|__version__)\s*=\s*['\"]([^'\"]+)['\"]", path.read_text(encoding='utf-8-sig'))
    return match[1] if match else None


def read_desktop_marker(root):
    path = Path(root) / MARKER
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or not isinstance(value.get('package'), str) or not isinstance(value.get('source'), str):
            raise ValueError('package/source harus string')
        return value
    except (OSError, ValueError) as exc:
        return {'invalid': True, 'error': str(exc)}


def duplicate_desktop_copies(desktop_root):
    """Inventory only the selected Desktop plugin directory, never the whole disk."""
    target = Path(desktop_root)
    found = []
    if target.parent.is_dir():
        for folder in sorted(target.parent.iterdir()):
            if folder == target or folder.is_symlink() or not folder.is_dir():
                continue
            entry = folder / 'plugin.js'
            if entry.is_file() and not entry.is_symlink():
                if re.search(r"\bid\s*:\s*['\"]" + re.escape(PLUGIN_ID) + r"['\"]", entry.read_text(encoding='utf-8-sig', errors='replace')):
                    found.append(str(folder))
    return found


def compare_desktop(runtime_root, installed_root, desktop_root):
    source = Path(runtime_root).resolve() / 'desktop' / 'plugin.js'
    target = Path(desktop_root).expanduser().resolve()
    entry = target / 'plugin.js'
    marker = read_desktop_marker(target)
    matches = source.is_file() and entry.is_file() and _digest(source) == _digest(entry)
    management = 'missing' if not entry.is_file() else 'standalone' if marker is None else 'invalid' if marker.get('invalid') else 'managed'
    expected_source = (Path(installed_root).expanduser().resolve() / 'desktop')
    marker_matches = management == 'managed' and marker.get('package') == PLUGIN_ID and Path(marker['source']).expanduser().resolve() == expected_source
    duplicates = duplicate_desktop_copies(target)
    warnings = []
    if management == 'standalone':
        warnings.append('Popup mandiri tidak diperbarui otomatis oleh Hermes. Gunakan --adopt-desktop setelah meninjau backup/target.')
    if management in {'managed', 'invalid'} and not marker_matches:
        warnings.append('Marker Desktop rusak atau menunjuk paket/profil lain. Jangan menganggap kode yang sama akan tetap sinkron.')
    if duplicates:
        warnings.append('ID plugin juga muncul di folder Desktop lain; tinjau di Capabilities sebelum sinkronisasi.')
    return {'success': bool(matches and not duplicates and (management == 'standalone' or marker_matches)),
            'desktop_plugin_root': str(target), 'entry_exists': entry.is_file(), 'code_matches': bool(matches),
            'runtime_version': _version(source), 'desktop_version': _version(entry), 'management': management,
            'marker_matches_backend': bool(marker_matches), 'duplicate_plugin_roots': duplicates, 'warnings': warnings,
            'loaded_process_checked': False}


def compare_installation(runtime_root, installed_root, desktop_root=None):
    runtime = Path(runtime_root).expanduser().resolve()
    installed = Path(installed_root).expanduser().resolve()
    files = {Path('__init__.py'), Path('plugin.yaml')}
    if (runtime / 'scanner/live_tools.py').is_file():
        files.update((Path('dashboard/manifest.json'), Path('dashboard/plugin_api.py')))
    for folder, pattern in (('scanner', '*.py'), ('desktop', '*.js'), ('docs', '*.md'), ('dashboard', '*.py'), ('dashboard', '*.json')):
        files.update(path.relative_to(runtime) for path in (runtime / folder).rglob(pattern))
    missing_source, missing_installed, different = [], [], []
    for relative in sorted(files):
        source, target = runtime / relative, installed / relative
        label = relative.as_posix()
        if not source.is_file():
            missing_source.append(label)
        elif not target.is_file():
            missing_installed.append(label)
        elif _digest(source) != _digest(target):
            different.append(label)
    result = {'success': not (missing_source or missing_installed or different),
        'runtime_root': str(runtime), 'installed_plugin_root': str(installed),
        'installed_exists': installed.is_dir(), 'compared_file_count': len(files),
        'missing_runtime_files': missing_source, 'missing_installed_files': missing_installed,
        'different_files': different,
        'legacy_installed_files': [name for name in LEGACY if (installed / name).is_file()],
        'loaded_process_checked': False,
        'instruction': 'Perbandingan file disk saja. Setelah sync, restart Hermes/gateway dan reload Desktop; proses lama tidak berubah otomatis.'}
    if desktop_root is not None:
        result['desktop'] = compare_desktop(runtime, installed, desktop_root)
        result['success'] = result['success'] and result['desktop']['success']
    return result
