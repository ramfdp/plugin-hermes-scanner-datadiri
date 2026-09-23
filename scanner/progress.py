"""Small, private progress snapshots. No OCR text, personal data or document paths.

Workers write atomic snapshots; the authenticated Hermes plugin API reads them
without the review lock. The heartbeat proves a worker is alive, not advancing.
This module intentionally uses only stdlib so the gateway needs no OCR packages.
"""
import contextvars
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

PROTOCOL = 'scanner-progress-v1'
STAGES = {'setup', 'ocr', 'mapping', 'summary', 'web', 'analysis', 'reports', 'complete'}
STATUSES = {'running', 'waiting', 'complete', 'partial', 'error'}
COUNTERS = {'pages_done', 'pages_total', 'people_done', 'people_total', 'web_requests', 'web_failed', 'artifact_count'}
_current = contextvars.ContextVar('scanner_progress', default=None)


def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{32}', value) is not None


def output_root():
    project = Path(os.environ.get('HERMES_SCANNER_PROJECT') or Path(__file__).resolve().parents[1])
    return Path(os.environ.get('HERMES_SCANNER_OUTPUT_DIR') or project / 'output').expanduser().resolve()


def snapshot_path(progress_id):
    if not valid_id(progress_id):
        raise ValueError('PROGRESS_ID_INVALID')
    directory = output_root() / 'progress'
    path = directory / f'{progress_id}.json'
    # Do not follow a redirected progress directory or individual snapshot.
    if directory.is_symlink() or directory.resolve() != directory or path.is_symlink():
        raise ValueError('PROGRESS_PATH_INVALID')
    if hasattr(directory, 'is_junction') and (directory.is_junction() or path.is_junction()):
        raise ValueError('PROGRESS_PATH_INVALID')
    return path


def _read(path):
    if path.stat().st_size > 65536:
        raise ValueError('PROGRESS_TOO_LARGE')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('PROGRESS_INVALID')
    return data


def read_snapshot(progress_id):
    """Read-only, bounded public projection; never return worker exception text."""
    path = snapshot_path(progress_id)
    if not path.is_file():
        return None
    data = _read(path)
    if data.get('protocol') != PROTOCOL or data.get('progress_id') != progress_id:
        raise ValueError('PROGRESS_INVALID')
    if data.get('stage') not in STAGES or data.get('status') not in STATUSES:
        raise ValueError('PROGRESS_INVALID')
    result = {k: data.get(k) for k in ('protocol', 'progress_id', 'sequence', 'stage', 'status',
              'started_at', 'updated_at', 'heartbeat_at', 'worker_active')}
    for key in COUNTERS:
        value = data.get(key)
        result[key] = value if type(value) is int and value >= 0 else None
    result['steps_done'] = [s for s in data.get('steps_done', []) if s in STAGES]
    result['detail'] = data.get('detail') if data.get('detail') in {
        'loading_model', 'reading_pages', 'waiting_agent', 'generating_reports', 'retry_needed', 'done'} else None
    result['web_enabled'] = data.get('web_enabled') if isinstance(data.get('web_enabled'), bool) else None
    result['report_complete'] = data.get('report_complete') is True
    return result


def _mutate(progress_id, change):
    path = snapshot_path(progress_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    deadline = time.monotonic() + 0.5
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError('PROGRESS_BUSY')
            time.sleep(0.01)
    temp = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        data = _read(path) if path.exists() else {}
        value = change(data)
        if value is None:
            return
        value['sequence'] = data.get('sequence', 0) + 1
        temp.write_text(json.dumps(value, allow_nan=False), encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)


class Tracker:
    """One operation owns writes. Late heartbeats cannot overwrite a newer call."""
    def __init__(self, progress_id, run_id, operation_id=None):
        self.id, self.run_id = progress_id, run_id
        self.operation = operation_id if valid_id(operation_id) else uuid.uuid4().hex
        self.stop = threading.Event()
        self.thread = None
        self.active = False

    def begin(self, stage):
        def start(old):
            if old.get('run_id') and self.run_id and old['run_id'] != self.run_id:
                raise ValueError('PROGRESS_ALREADY_BOUND')
            now = time.time()
            return {**old, 'protocol': PROTOCOL, 'progress_id': self.id, 'run_id': self.run_id or old.get('run_id'),
                    'operation_id': self.operation, 'stage': stage, 'status': 'running',
                    'started_at': old.get('started_at', now), 'updated_at': now, 'heartbeat_at': now,
                    'worker_active': True, 'detail': None}
        _mutate(self.id, start)
        self.active = True
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()

    def put(self, **fields):
        # Only callers in this module can add identifiers. Text is limited to fixed codes.
        allowed = COUNTERS | {'stage', 'status', 'steps_done', 'detail', 'worker_active', 'report_complete', 'web_enabled'}
        fields = {key: value for key, value in fields.items() if key in allowed}
        def update(old):
            if old.get('operation_id') != self.operation:
                return None
            return {**old, **fields, 'updated_at': time.time(), 'heartbeat_at': time.time()}
        try:
            _mutate(self.id, update)
        except (OSError, ValueError, TimeoutError):
            # Broken telemetry must not destroy OCR or report artifacts.
            pass

    def bind(self, run_id):
        def update(old):
            if old.get('operation_id') != self.operation:
                return None
            if old.get('run_id') not in (None, run_id):
                raise ValueError('PROGRESS_ALREADY_BOUND')
            return {**old, 'run_id': run_id}
        _mutate(self.id, update)
        self.run_id = run_id

    def _heartbeat(self):
        while not self.stop.wait(5):
            def update(old):
                if old.get('operation_id') != self.operation or not old.get('worker_active'):
                    return None
                return {**old, 'heartbeat_at': time.time()}
            try:
                _mutate(self.id, update)
            except (OSError, ValueError, TimeoutError):
                pass

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=1)
        self.put(worker_active=False)


@contextmanager
def tracking(progress_id, run_id, stage, operation_id=None):
    tracker = Tracker(progress_id, run_id, operation_id) if progress_id else None
    token = _current.set(tracker)
    try:
        if tracker:
            try:
                tracker.begin(stage)
            except (OSError, ValueError, TimeoutError):
                # Still run the requested work. UI detects unavailable/stale telemetry.
                tracker = None
                _current.set(None)
        yield tracker
    except BaseException:
        if tracker:
            tracker.put(status='error', detail='retry_needed')
        raise
    finally:
        if tracker:
            tracker.close()
        _current.reset(token)


def active():
    return _current.get() is not None


def emit(**fields):
    tracker = _current.get()
    if tracker:
        tracker.put(**fields)


def interrupted(progress_id, operation_id):
    """Called only after subprocess failure/timeout; never guess a worker died."""
    if valid_id(progress_id) and valid_id(operation_id):
        tracker = Tracker(progress_id, None, operation_id)
        tracker.put(status='error', detail='retry_needed', worker_active=False)
