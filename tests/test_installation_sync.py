"""Temporary-directory tests; never touch the operator's Hermes home or GPU."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scanner.installation import PLUGIN_ID, MARKER, locations, compare_installation, compare_desktop

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scanner_sync_test_module', REPO / 'scripts' / 'sync_plugin.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / 'runtime'
        self.home = self.base / 'hermes'
        self.backend = self.home / 'plugins' / PLUGIN_ID
        self.desktop = self.home / 'desktop-plugins' / PLUGIN_ID
        for relative, content in {
            '__init__.py': '# package\n', 'plugin.yaml': f'name: {PLUGIN_ID}\nversion: 0.4.2\n',
            'scanner/__init__.py': '__version__ = "0.4.2"\n', 'scanner/tools.py': 'version = 2\n',
            'desktop/plugin.js': f"const VERSION = '0.4.2'\nexport default {{ id: '{PLUGIN_ID}' }}\n",
            'docs/debug.md': 'Read-only diagnostics.\n', 'requirements/base.txt': '# test\n', 'requirements.txt': '# test\n',
        }.items():
            p = self.root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding='utf-8')
        self.backend.mkdir(parents=True)
        (self.backend / 'tools.py').write_text('legacy = True\n')
        self.desktop.mkdir(parents=True)
        (self.desktop / 'plugin.js').write_text(f"export default {{ id: '{PLUGIN_ID}', name: 'old' }}\n")

    def plan(self, **kwargs):
        return sync.plan_sync(self.root, hermes_home=self.home, **kwargs)

    def snapshot(self, root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_preview_has_zero_writes_and_identifies_standalone(self):
        before = self.snapshot(self.base)
        plan = self.plan()
        self.assertTrue(plan['requires_adoption'])
        self.assertEqual(self.snapshot(self.base), before)
        self.assertFalse((self.root / 'output').exists())

    def test_unmanaged_popup_requires_explicit_adoption_before_any_write(self):
        before = self.snapshot(self.base)
        with self.assertRaisesRegex(ValueError, 'ADOPTION_REQUIRED'):
            sync.apply_sync(self.plan())
        self.assertEqual(before, self.snapshot(self.base))

    def test_adoption_updates_both_locations_and_keeps_backups_and_user_data(self):
        originals = {}
        for relative in ('models/weights.bin', 'output/result.txt', '.env', '.git/config', '.venv/keep', 'my-custom.txt'):
            p = self.backend / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('DO NOT MODIFY')
            originals[p] = p.read_bytes()
        old_popup = (self.desktop / 'plugin.js').read_bytes()
        result = sync.apply_sync(self.plan(adopt_desktop=True))
        self.assertTrue(result['success'], result)
        backup = Path(result['backup'])
        self.assertEqual((backup / 'desktop/plugin.js').read_bytes(), old_popup)
        self.assertEqual((backup / 'backend/tools.py').read_text(), 'legacy = True\n')
        self.assertFalse((self.backend / 'tools.py').exists())
        for p, content in originals.items(): self.assertEqual(p.read_bytes(), content)
        marker = json.loads((self.desktop / MARKER).read_text())
        self.assertEqual(marker['package'], PLUGIN_ID)
        self.assertEqual(Path(marker['source']), self.backend / 'desktop')
        self.assertAlmostEqual(marker['sourceMtimeMs'], (self.backend / 'desktop/plugin.js').stat().st_mtime_ns / 1_000_000, delta=1)
        self.assertTrue(compare_installation(self.root, self.backend, self.desktop)['success'])

    def test_managed_desktop_can_be_synced_again_without_adoption(self):
        sync.apply_sync(self.plan(adopt_desktop=True))
        (self.root / 'desktop/plugin.js').write_text(f"const VERSION='0.4.3'\nexport default {{id:'{PLUGIN_ID}'}}\n")
        result = sync.apply_sync(self.plan())
        self.assertTrue(result['success'])
        self.assertEqual(result['installation']['desktop']['desktop_version'], '0.4.3')

    def test_correct_backend_but_stale_app_popup_is_not_success(self):
        sync.apply_sync(self.plan(adopt_desktop=True))
        (self.desktop / 'plugin.js').write_text('old code')
        self.assertTrue(compare_installation(self.root, self.backend)['success'])
        result = compare_installation(self.root, self.backend, self.desktop)
        self.assertFalse(result['success'])
        self.assertFalse(result['desktop']['code_matches'])
        self.assertFalse(result['loaded_process_checked'])

    def test_desktop_crlf_and_lf_are_equal_but_wrong_marker_is_reported(self):
        sync.apply_sync(self.plan(adopt_desktop=True))
        source = (self.root / 'desktop/plugin.js').read_bytes()
        (self.desktop / 'plugin.js').write_bytes(source.replace(b'\n', b'\r\n'))
        self.assertTrue(compare_desktop(self.root, self.backend, self.desktop)['success'])
        marker = json.loads((self.desktop / MARKER).read_text())
        marker['source'] = str(self.base / 'another-profile/desktop')
        (self.desktop / MARKER).write_text(json.dumps(marker))
        self.assertFalse(compare_desktop(self.root, self.backend, self.desktop)['success'])
        self.assertTrue(self.plan()['requires_adoption'])

    def test_profile_home_resolves_backend_separately_from_app_home(self):
        home = self.home / 'profiles/office'
        resolved = locations(self.root, hermes_home=home)
        self.assertEqual(resolved['backend'], home / 'plugins' / PLUGIN_ID)
        self.assertEqual(resolved['desktop'], self.desktop)
        override = locations(self.root, hermes_home=home, desktop_home=self.base / 'app2')
        self.assertEqual(override['desktop'], self.base / 'app2/desktop-plugins' / PLUGIN_ID)
        self.assertEqual(locations(self.root, hermes_home=home, desktop_plugin_dir=self.desktop)['desktop'], self.desktop)

    def test_other_plugin_and_duplicate_ids_are_never_overwritten(self):
        (self.desktop / 'plugin.js').write_text("export default { id:'different-plugin' }")
        with self.assertRaisesRegex(ValueError, 'plugin lain'):
            self.plan(adopt_desktop=True)
        (self.desktop / 'plugin.js').write_text(f"export default {{ id:'{PLUGIN_ID}' }}")
        other = self.desktop.parent / 'old-scanner'
        other.mkdir(); (other / 'plugin.js').write_text(f"export default {{ id:'{PLUGIN_ID}' }}")
        with self.assertRaisesRegex(ValueError, 'duplikat'):
            self.plan(adopt_desktop=True)
        report = compare_desktop(self.root, self.backend, self.desktop)
        self.assertEqual(report['duplicate_plugin_roots'], [str(other)])

    def test_marker_from_other_package_is_not_adopted(self):
        (self.desktop / MARKER).write_text(json.dumps({'package': 'other', 'source': 'other'}))
        with self.assertRaisesRegex(ValueError, 'paket lain'):
            self.plan(adopt_desktop=True)

    def test_backend_missing_or_targets_overlapping_fail_before_writing(self):
        with self.assertRaisesRegex(ValueError, 'belum terpasang'):
            self.plan(plugin_dir=self.base / 'missing')
        with self.assertRaisesRegex(ValueError, 'di dalamnya'):
            self.plan(desktop_plugin_dir=self.backend / 'desktop-plugins' / PLUGIN_ID)

    def test_runtime_can_already_be_installed_without_self_copy_or_deleting_legacy(self):
        (self.root / 'tools.py').write_text('operator shim\n')
        plan = self.plan(plugin_dir=self.root, adopt_desktop=True)
        self.assertTrue(all(op['group'] == 'desktop' for op in plan['operations']))
        result = sync.apply_sync(plan)
        self.assertTrue(result['success'])
        self.assertEqual((self.root / 'tools.py').read_text(), 'operator shim\n')

    def test_targets_changed_after_preview_are_not_overwritten(self):
        plan = self.plan(adopt_desktop=True)
        (self.desktop / 'plugin.js').write_text('new manual edit')
        with self.assertRaisesRegex(RuntimeError, 'berubah'):
            sync.apply_sync(plan)
        self.assertEqual((self.desktop / 'plugin.js').read_text(), 'new manual edit')
        self.assertFalse((self.root / 'output').exists())

    def test_failed_publish_rolls_back_files_already_updated(self):
        before = self.snapshot(self.home)
        real_replace = os.replace
        def replace(src, dst):
            if Path(dst) == self.desktop / 'plugin.js': raise PermissionError('simulated file lock')
            return real_replace(src, dst)
        with patch.object(sync.os, 'replace', side_effect=replace), self.assertRaisesRegex(RuntimeError, 'Backup:'):
            sync.apply_sync(self.plan(adopt_desktop=True))
        self.assertEqual(self.snapshot(self.home), before)
        self.assertTrue(list((self.root / 'output').glob('plugin-backup-*/manifest.json')))

    def test_symlink_sources_or_target_ancestors_are_rejected(self):
        source = self.root / 'scanner/tools.py'
        source.unlink()
        try:
            source.symlink_to(self.backend / 'tools.py')
        except OSError:
            # Some Windows accounts do not have symlink privilege. Test the reparse branch below as well.
            source.write_text('version=2\n')
            class ReparseStat:
                st_mode = stat_mode = 0
                st_file_attributes = 1024
            with patch.object(Path, 'lstat', return_value=ReparseStat()), self.assertRaisesRegex(ValueError, 'junction'):
                sync.no_links(source)
        else:
            with self.assertRaisesRegex(ValueError, 'junction'): self.plan(adopt_desktop=True)

    def test_missing_desktop_copy_is_created_with_marker(self):
        shutil.rmtree(self.desktop)
        self.assertFalse(self.plan()['requires_adoption'])
        self.assertTrue(sync.apply_sync(self.plan())['success'])

    def test_powershell_whatif_and_apply_wrapper(self):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell not present locally; this wrapper runs on Windows CI')
        scripts = self.root / 'scripts'; scripts.mkdir()
        for name in ('sync_plugin.py', 'sync_plugin.ps1'):
            shutil.copy2(REPO / 'scripts' / name, scripts / name)
        shutil.copy2(REPO / 'scanner/installation.py', self.root / 'scanner/installation.py')
        command = [shell, '-NoProfile', '-File', str(scripts / 'sync_plugin.ps1'), '-PythonExe', sys.executable,
                   '-HermesHome', str(self.home), '-AdoptDesktop']
        before = self.snapshot(self.home)
        preview = subprocess.run([*command, '-WhatIf'], capture_output=True, text=True, timeout=30)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertEqual(before, self.snapshot(self.home))
        self.assertFalse((self.root / 'output').exists())
        applied = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertTrue(compare_installation(self.root, self.backend, self.desktop)['success'])


if __name__ == '__main__':
    unittest.main()
