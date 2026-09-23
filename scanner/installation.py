"""Read-only comparison of runtime checkout and the installed Hermes plugin."""
import hashlib
from pathlib import Path

LEGACY = ('tools.py', 'schemas.py', 'ocr_runner.py', 'exporter.py', 'cv_report.py')


def _digest(path):
    # Git checkouts on Windows can use CRLF; this is a code comparison, not a file signature.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def compare_installation(runtime_root, installed_root):
    runtime = Path(runtime_root).expanduser().resolve()
    installed = Path(installed_root).expanduser().resolve()
    files = {Path('__init__.py'), Path('plugin.yaml')}
    for folder, pattern in (('scanner', '*.py'), ('desktop', '*.js'), ('docs', '*.md')):
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
    return {'success': not (missing_source or missing_installed or different),
        'runtime_root': str(runtime), 'installed_plugin_root': str(installed),
        'installed_exists': installed.is_dir(), 'compared_file_count': len(files),
        'missing_runtime_files': missing_source, 'missing_installed_files': missing_installed,
        'different_files': different,
        'legacy_installed_files': [name for name in LEGACY if (installed / name).is_file()],
        'loaded_process_checked': False,
        'instruction': 'Perbandingan file disk saja. Setelah sync, restart Hermes/gateway dan reload Desktop; proses lama tidak berubah otomatis.'}
