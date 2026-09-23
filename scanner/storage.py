"""Local run storage, atomic checkpoints and cross-process exclusion."""
import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def output_root():
    return Path(os.environ.get("HERMES_SCANNER_OUTPUT_DIR", str(Path(os.environ.get("HERMES_SCANNER_PROJECT", str(PROJECT_ROOT))) / "output"))).expanduser().resolve()


def run_dir(run_id):
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("run_id harus ID yang dikembalikan action start")
    root = (output_root() / "reviews").resolve()
    path = root / run_id
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("Lokasi run tidak valid")
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


@contextmanager
def locked(run_id):
    root = run_dir(run_id)
    if not (root / "manifest.json").is_file():
        raise FileNotFoundError("Run tidak ditemukan")
    lock = root / ".lock"
    deadline = time.monotonic() + 5
    while True:
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError("RUN_BUSY: operasi lain berjalan; jangan hapus lock saat proses masih aktif")
            time.sleep(0.05)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "at": now()}))
        yield root
    finally:
        lock.unlink(missing_ok=True)


def event(root, action, **counts):
    # No document text, names, certificate numbers, paths, or provider credentials in logs.
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "action": action, **counts}) + "\n")
