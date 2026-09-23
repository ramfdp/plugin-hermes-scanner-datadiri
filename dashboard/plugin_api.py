"""Authenticated Hermes plugin namespace. Read-only telemetry, never scan/upload."""
import importlib.util
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response

# Hermes loads plugin_api.py by file path, not as part of our Python package.
# Load only the fixed stdlib-only reader beside this trusted installed package.
_module_path = Path(__file__).resolve().parents[1] / 'scanner' / 'progress.py'
_spec = importlib.util.spec_from_file_location('_hermes_scanner_progress_api', _module_path)
progress = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(progress)
router = APIRouter()


@router.get('/progress/{progress_id}')
def get_progress(progress_id: str, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    if not progress.valid_id(progress_id):
        raise HTTPException(status_code=400, detail='PROGRESS_ID_INVALID')
    try:
        snapshot = progress.read_snapshot(progress_id)
    except (OSError, ValueError):
        raise HTTPException(status_code=503, detail='PROGRESS_UNAVAILABLE') from None
    return {'success': True, 'found': snapshot is not None, 'protocol': progress.PROTOCOL, 'snapshot': snapshot}
