"""Progress adapter around the unchanged Excel-first workflow engine."""
import json
import sys
from . import progress, storage, workflow

READ_ACTIONS = {'health', 'help', 'status', 'read_receipt'}
STAGES = {'start': 'setup', 'document': 'ocr', 'read_document': 'mapping', 'plan': 'mapping',
          'summary': 'summary', 'verify_kak': 'web', 'save_person': 'analysis', 'export': 'reports'}


def tracking_id(args):
    if args.get('action') == 'start':
        value = args.get('payload', {}).get('progress_id')
    elif args.get('run_id'):
        value = storage.load(storage.run_dir(args['run_id']) / 'manifest.json').get('progress_id')
    else:
        value = None
    if value is not None and not progress.valid_id(value):
        raise ValueError('PROGRESS_ID_INVALID')
    return value


def facts(run_id):
    """Only counts and checkpoint states, never evidence or person identifiers."""
    root = storage.run_dir(run_id)
    manifest = storage.load(root / 'manifest.json')
    plan = storage.load(root / 'plan.json') if (root / 'plan.json').exists() else {}
    states = [storage.load(root / 'ocr' / f"{d['id']}.json") if (root / 'ocr' / f"{d['id']}.json").exists()
              else {} for d in manifest['documents']]
    steps = []
    if states and all(s.get('success') for s in states):
        steps.append('ocr')
    if plan:
        steps.append('mapping')
    if (root / 'summary.json').exists():
        steps.append('summary')
    people = plan.get('roster', [])
    saved = sum((root / 'people' / f"{p['id']}.json").is_file() for p in people)
    if people and saved == len(people):
        steps.append('analysis')
    receipts = [storage.load(path) for path in (root / 'web').glob('*.json')]
    # A web request completing is not the same as verifying a certificate.
    return {'steps_done': steps, 'people_done': saved, 'people_total': len(people) if plan else None,
            'web_enabled': manifest['allow_web'], 'web_requests': len(receipts), 'web_failed': sum(not r.get('success') for r in receipts)}


def finish(tracker, args, result):
    if not tracker:
        return
    run_id = result.get('run_id') or args.get('run_id')
    counts = facts(run_id) if run_id else {}
    action = args.get('action')
    if action == 'export':
        artifacts = result.get('artifacts', [])
        complete = result.get('workflow_complete') is True and len(artifacts) == 2
        if complete:
            counts['steps_done'] = [*counts.get('steps_done', []), *(['web'] if counts.get('web_enabled') else []), 'reports']
        tracker.put(**counts, status='complete' if complete else 'partial' if artifacts else 'error',
                    stage='complete' if complete else 'reports', artifact_count=len(artifacts),
                    detail='done' if complete else 'retry_needed', report_complete=result.get('report_complete', False))
    elif not result.get('success'):
        tracker.put(**counts, status='error', detail='retry_needed')
    else:
        next_stage = {'start': 'ocr', 'document': 'mapping', 'read_document': 'mapping', 'plan': 'summary',
                      'summary': 'web', 'verify_kak': 'analysis', 'save_person': 'analysis'}.get(action, 'setup')
        if action == 'document':
            # An incomplete multi-document run stays in OCR; no all-pages claim.
            if 'ocr' not in counts.get('steps_done', []):
                next_stage = 'ocr'
            if type(result.get('page_count')) is int:
                tracker.put(pages_done=result['page_count'], pages_total=result['page_count'])
        tracker.put(**counts, stage=next_stage, status='waiting', detail='waiting_agent')


def dispatch(args):
    if args.get('action') in READ_ACTIONS:
        return workflow.dispatch(args)
    pid = tracking_id(args)
    if args.get('action') == 'start' and pid:
        existing = progress.snapshot_path(pid)
        if existing.is_file() and progress._read(existing).get('run_id'):
            raise ValueError('PROGRESS_ALREADY_BOUND: gunakan run yang sudah dimulai, jangan membuat run kedua')
    with progress.tracking(pid, args.get('run_id'), STAGES.get(args.get('action'), 'setup'),
                           args.get('_progress_operation')) as tracker:
        try:
            result = workflow.dispatch(args)
            if args.get('action') == 'start' and result.get('success') and pid:
                with storage.locked(result['run_id']) as root:
                    manifest = storage.load(root / 'manifest.json')
                    manifest['progress_id'] = pid
                    storage.save(root / 'manifest.json', manifest)
                if tracker:
                    try:
                        tracker.bind(result['run_id'])
                    except (OSError, ValueError, TimeoutError):
                        pass
                result['progress_id'] = pid
            try:
                finish(tracker, args, result)
            except (OSError, ValueError, KeyError):
                pass  # A progress read must not change the outcome of the work.
            return result
        except Exception:
            if tracker:
                tracker.put(status='error', detail='retry_needed')
            raise


def main():
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    try:
        result = dispatch(json.load(sys.stdin))
    except Exception as exc:
        result = {'success': False, 'workflow_complete': False, 'error': type(exc).__name__, 'message': str(exc)}
    print('HERMES_REVIEW_RESULT=' + json.dumps(result, ensure_ascii=False), flush=True)
    if not result['success']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
