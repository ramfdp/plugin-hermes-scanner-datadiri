"""Hermes adapters for progress-aware workers; legacy tools remain unchanged."""
import os
import uuid
from . import __version__, progress, tools
from .live_worker import tracking_id, facts


def scanner_review(args: dict, **kwargs) -> str:
    operation = uuid.uuid4().hex
    pid = None
    try:
        pid = tracking_id(args)
        timeout = int(os.environ.get('HERMES_OCR_TIMEOUT_SECONDS', '7200')) + 120
        request = {**args, '_plugin_version': __version__, '_progress_operation': operation}
        result = tools._run_script('scanner.live_worker', 'REVIEW', [], payload=request, timeout=timeout)
        if not result.get('success'):
            # A controlled partial export already published an accurate terminal snapshot.
            # Its nonzero CLI exit is not an interrupted worker and must stay partial.
            if result.get('stage') != 'export_partial' or not result.get('artifacts'):
                progress.interrupted(pid, operation)
            result.setdefault('workflow_complete', False)
        return tools._result(result)
    except Exception as exc:
        progress.interrupted(pid, operation)
        return tools._result({'success': False, 'workflow_complete': False,
                              'error': type(exc).__name__, 'message': str(exc)})


def ordered_web_handler(ctx):
    native = tools.ordered_web_handler(ctx)
    async def handler(args, **kwargs):
        try:
            pid = tracking_id(args)
        except (OSError, ValueError, KeyError):
            pid = None
        with progress.tracking(pid, args.get('run_id'), 'web') as tracker:
            result = await native(args, **kwargs)
            if tracker:
                # Failure is a completed attempt with a limitation, not a counterfeit certificate.
                try:
                    tracker.put(**facts(args['run_id']), status='waiting', detail='waiting_agent')
                except (OSError, ValueError, KeyError):
                    pass
            return result
    return handler
