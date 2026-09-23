"""Fast pre-commit gate: conflict markers, Python syntax, CPU unit tests, Desktop tests."""
import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = [ROOT / '__init__.py']
    for directory in ('scanner', 'scripts', 'tests', 'desktop'):
        files.extend(p for p in (ROOT / directory).rglob('*') if p.suffix in {'.py', '.js', '.cjs', '.ps1'})
    failures = []
    for path in files:
        text = path.read_text(encoding='utf-8-sig')
        if re.search(r'^(?:<{7} |={7}$|>{7} )', text, re.MULTILINE):
            failures.append(f'Unresolved merge marker: {path.relative_to(ROOT)}')
        if path.suffix == '.py':
            try:
                ast.parse(text, filename=str(path))
            except SyntaxError as exc:
                failures.append(str(exc))
    if failures:
        print('\n'.join(failures))
        return 1
    print(f'Syntax and conflict check: {len(files)} files OK', flush=True)
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT)
    if result.returncode:
        return result.returncode
    if not shutil.which('node'):
        print('Node.js unavailable: Desktop tests NOT RUN. Install Node and rerun before merging.')
        return 2
    return subprocess.run(['node', '--test', 'tests/desktop.test.cjs'], cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
