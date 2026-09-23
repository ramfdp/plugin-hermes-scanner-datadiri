"""Preview by default; explicitly apply a backed-up backend AND Desktop sync.

No model, output, credentials, enable settings or Git history are modified.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scanner import __version__
from scanner.installation import PLUGIN_ID, MARKER, LEGACY, locations, read_desktop_marker, duplicate_desktop_copies, compare_installation

COPY_NAMES = ('__init__.py', 'plugin.yaml', 'scanner', 'desktop', 'dashboard', 'docs', 'requirements', 'requirements.txt')
OLD_NAMES = (*LEGACY, 'download_model.py', 'finish_migration.ps1', 'local_only_report.py')


def no_links(path):
    """Reject symlinks and Windows junctions in the entire path before copying."""
    path = Path(path).absolute()
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024):
            raise ValueError(f'Link/junction tidak disinkronkan: {item}')
    return path


def fingerprint(path):
    no_links(path)
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f'Target bukan file: {path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_sync(runtime_root=ROOT, *, adopt_desktop=False, **options):
    places = locations(runtime_root, **options)
    for path in places.values():
        no_links(path)
    root, backend, desktop = (places[k].resolve() for k in ('runtime', 'backend', 'desktop'))
    if not backend.is_dir():
        raise ValueError(f'Paket plugin belum terpasang: {backend}. Periksa home/profil, jangan membuat instalasi ke lokasi tebakan.')
    for a, b in ((root, backend), (root, desktop), (backend, desktop)):
        if a == b:
            if a == root and b == backend:
                continue
            raise ValueError('Target Desktop tidak boleh sama dengan runtime/backend')
        if a in b.parents or b in a.parents:
            raise ValueError('Folder source/backend/Desktop tidak boleh saling berada di dalamnya')
    if desktop.name != PLUGIN_ID:
        raise ValueError(f'Nama folder Desktop harus {PLUGIN_ID}')
    duplicates = duplicate_desktop_copies(desktop)
    if duplicates:
        raise ValueError('ID plugin duplikat; tinjau folder ini tanpa menghapus otomatis: ' + ', '.join(duplicates))
    no_links(desktop / MARKER)
    marker = read_desktop_marker(desktop)
    if marker and not marker.get('invalid') and marker['package'] != PLUGIN_ID:
        raise ValueError('Marker Desktop milik paket lain; sinkronisasi dibatalkan')
    managed_here = marker and not marker.get('invalid') and Path(marker['source']).expanduser().resolve() == backend / 'desktop'
    requires_adoption = desktop.exists() and not managed_here
    entry = desktop / 'plugin.js'
    if entry.is_file() and not managed_here:
        no_links(entry)
        if not re.search(r"\bid\s*:\s*['\"]" + re.escape(PLUGIN_ID) + r"['\"]", entry.read_text(encoding='utf-8-sig')):
            raise ValueError('plugin.js target tidak mendeklarasikan ID Scanner; tidak menimpa plugin lain')
    if (root / 'scanner/live_tools.py').is_file():
        for name in ('manifest.json', 'plugin_api.py'):
            if not (root / 'dashboard' / name).is_file():
                raise ValueError(f'Source API progres tidak lengkap: dashboard/{name}')
    operations = []
    for name in COPY_NAMES:
        source = root / name
        no_links(source)
        if not source.exists():
            if name == 'dashboard' and not (root / 'scanner/live_tools.py').is_file():
                continue  # Compatibility with packages predating live progress.
            raise ValueError(f'Source tidak lengkap: {name}')
        files = [source] if source.is_file() else sorted(source.rglob('*'))
        for file in files:
            if '__pycache__' in file.parts or file.suffix in {'.pyc', '.pyo'}:
                continue
            no_links(file)
            if not file.is_file():
                continue
            relative = file.relative_to(root)
            if root != backend:
                operations.append({'source': file, 'target': backend / relative, 'group': 'backend', 'relative': relative})
            if relative.parts[0] == 'desktop' and relative.name != MARKER:
                rel = file.relative_to(root / 'desktop')
                operations.append({'source': file, 'target': desktop / rel, 'group': 'desktop', 'relative': rel})
    if not (root / 'desktop' / 'plugin.js').is_file():
        raise ValueError('Source desktop/plugin.js tidak tersedia')
    marker_data = {'package': PLUGIN_ID, 'source': str(backend / 'desktop'),
                   'sourceMtimeMs': (root / 'desktop' / 'plugin.js').stat().st_mtime_ns / 1_000_000}
    operations.append({'bytes': (json.dumps(marker_data, indent=2) + '\n').encode(), 'target': desktop / MARKER,
                       'group': 'desktop', 'relative': Path(MARKER)})
    if root != backend:
        for name in OLD_NAMES:
            old = backend / name
            if old.exists():
                operations.append({'delete': True, 'target': old, 'group': 'backend', 'relative': Path(name)})
    for op in operations:
        op['before'] = fingerprint(op['target'])
        if 'source' in op:
            op['source_hash'] = fingerprint(op['source'])
    return {'places': places, 'requires_adoption': bool(requires_adoption), 'adopt_desktop': adopt_desktop, 'operations': operations}


def apply_sync(plan):
    if plan['requires_adoption'] and not plan['adopt_desktop']:
        raise ValueError('DESKTOP_ADOPTION_REQUIRED: tinjau target, lalu gunakan --adopt-desktop untuk mengganti popup mandiri/provenance lama dengan backup.')
    root = plan['places']['runtime']
    backup = root / 'output' / ('plugin-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8])
    no_links(backup)
    # Validate all targets again before making any changes; previews are not locks.
    for op in plan['operations']:
        if fingerprint(op['target']) != op['before']:
            raise RuntimeError(f'Target berubah sejak preview: {op["target"]}')
        if 'source' in op and fingerprint(op['source']) != op['source_hash']:
            raise RuntimeError('Source berubah selama persiapan sinkronisasi')
    backup.mkdir(parents=True, exist_ok=False)
    applied = []
    with tempfile.TemporaryDirectory(prefix='staging-', dir=backup) as work:
        for number, op in enumerate(plan['operations']):
            if op['before'] is not None:
                old = backup / op['group'] / op['relative']
                old.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(op['target'], old)
            if not op.get('delete'):
                staged = Path(work) / str(number)
                if 'source' in op:
                    shutil.copy2(op['source'], staged)
                    if fingerprint(staged) != op['source_hash']:
                        raise RuntimeError('Source berubah ketika disalin; target belum diperbarui')
                else:
                    staged.write_bytes(op['bytes'])
                op['staged'] = staged
        manifest = [{'target': str(o['target']), 'backup': str(backup / o['group'] / o['relative']) if o['before'] is not None else None,
                     'operation': 'remove_legacy' if o.get('delete') else 'replace', 'previous_sha256': o['before']} for o in plan['operations']]
        (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        try:
            for op in plan['operations']:
                target = op['target']
                if fingerprint(target) != op['before']:
                    raise RuntimeError(f'Target berubah selama sinkronisasi: {target}')
                target.parent.mkdir(parents=True, exist_ok=True)
                if op.get('delete'):
                    target.unlink()
                else:
                    # Stage on the destination filesystem so os.replace also works across drives.
                    fd, temporary = tempfile.mkstemp(prefix='.scanner-sync-', dir=target.parent)
                    os.close(fd)
                    try:
                        shutil.copy2(op['staged'], temporary)
                        os.replace(temporary, target)
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                applied.append(op)
        except Exception as exc:
            rollback_errors = []
            for op in reversed(applied):
                try:
                    no_links(op['target'])
                    if op['before'] is None:
                        op['target'].unlink(missing_ok=True)
                    else:
                        shutil.copy2(backup / op['group'] / op['relative'], op['target'])
                except (OSError, ValueError) as restore_error:
                    rollback_errors.append(str(restore_error))
            raise RuntimeError(f'Sync gagal: {exc}. Backup: {backup}. Rollback errors: {rollback_errors}') from exc
    result = compare_installation(root, plan['places']['backend'], plan['places']['desktop'])
    return {'success': result['success'], 'backup': str(backup), 'installation': result,
            'next': f'Restart Hermes/backend agar API progres dimuat, lalu Reload desktop plugins. Pastikan popup v{__version__}. Pengaturan enable tidak diubah.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Tanpa flag ini hanya preview, tidak ada file ditulis')
    parser.add_argument('--adopt-desktop', action='store_true', help='Izinkan penggantian popup mandiri/marker lama Scanner setelah backup')
    for name in ('hermes-home', 'desktop-home', 'plugin-dir', 'desktop-plugin-dir'):
        parser.add_argument('--' + name, type=Path)
    args = vars(parser.parse_args())
    apply = args.pop('apply')
    try:
        plan = plan_sync(**args)
        result = apply_sync(plan) if apply else {'success': True, 'dry_run': True,
            'paths': {k: str(v) for k, v in plan['places'].items()},
            'requires_desktop_adoption': plan['requires_adoption'],
            'writes': [str(op['target']) for op in plan['operations'] if not op.get('delete')],
            'legacy_files_to_backup_and_remove': [str(op['target']) for op in plan['operations'] if op.get('delete')],
            'instruction': 'Periksa lokasi. --apply melakukan backup dan sync; --adopt-desktop diperlukan untuk popup mandiri/provenance berbeda.'}
    except Exception as exc:
        result = {'success': False, 'error': type(exc).__name__, 'message': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
