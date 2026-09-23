"""Explicit online setup. OCR never downloads a model during document processing."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scanner.ocr import DEFAULT_MODEL_DIR, MODEL_ID

MODEL_REVISION = 'd3f5e08d073c21466bbabe21c71bb1e9c2e595da'


def main():
    model_dir = Path(os.environ.get('HERMES_MINERU_MODEL_DIR', str(DEFAULT_MODEL_DIR))).expanduser().resolve()
    os.environ['HF_HOME'] = str(model_dir.parent / '.hf-cache')
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=model_dir, max_workers=3)
    print(f'Model ready for offline OCR: {model_dir}')


if __name__ == '__main__':
    main()
