import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
MODEL_ID = "opendatalab/MinerU2.5-Pro-2604-1.2B"
DEFAULT_MODEL_DIR = BASE_DIR / "models" / MODEL_ID.split("/")[-1]
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".pdf"}


def send_result(data):
    print("HERMES_OCR_RESULT=" + json.dumps(data, ensure_ascii=False), flush=True)


def read_markdown_files(files):
    contents = []
    for index, file_path in enumerate(files, start=1):
        text = Path(file_path).read_text(encoding="utf-8")
        contents.append(f"\n--- PAGE {index} ---\n{text}" if len(files) > 1 else text)
    return "\n".join(contents).strip()


def read_json_files(files):
    return [json.loads(Path(path).read_text(encoding="utf-8-sig")) for path in files]


def page_sort_key(path):
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name)]


def build_mineru_client(model_dir):
    model_dir = Path(model_dir).expanduser().resolve()
    for name in ("config.json", "model.safetensors", "tokenizer.json", "preprocessor_config.json"):
        if not (model_dir / name).is_file():
            raise FileNotFoundError(f"Model lokal belum lengkap: {model_dir / name}. Jalankan python scripts/download_model.py")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["LOGURU_LEVEL"] = "WARNING"
    import torch
    from mineru_vl_utils import MinerUClient
    from mineru_vl_utils.transformers_loading import load_transformers_model, load_transformers_processor
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch CUDA/GPU tidak tersedia. Pasang wheel CUDA sesuai README; tidak fallback ke CPU.")
    model = load_transformers_model(str(model_dir), device_map={"": "cuda:0"})
    model.eval()
    processor = load_transformers_processor(str(model_dir))
    return MinerUClient(backend="transformers", model=model, processor=processor,
                        batch_size=1, max_concurrency=1, use_tqdm=False, image_analysis=False)


def iter_page_images(input_path):
    from PIL import Image, ImageOps, ImageSequence
    if input_path.suffix.lower() == ".pdf":
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(input_path))
        try:
            for index in range(len(document)):
                page = document[index]
                try:
                    bitmap = page.render(scale=200 / 72)
                    try:
                        image = bitmap.to_pil().convert("RGB")
                        try:
                            yield image
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        finally:
            document.close()
    else:
        with Image.open(input_path) as source:
            for frame in ImageSequence.Iterator(source):
                with ImageOps.exif_transpose(frame).convert("RGB") as image:
                    yield image


def _page_total(input_path):
    """Count pages without rasterizing; an unreadable count stays unknown."""
    try:
        if input_path.suffix.lower() == '.pdf':
            import pypdfium2 as pdfium
            with pdfium.PdfDocument(str(input_path)) as document:
                return len(document)
        from PIL import Image
        with Image.open(input_path) as image:
            return getattr(image, 'n_frames', 1)
    except Exception:
        return None


def run_mineru(input_path, output_dir, model_dir):
    from . import progress
    total = _page_total(input_path) if progress.active() else None
    progress.emit(stage='ocr', pages_done=0, pages_total=total, detail='loading_model')
    client = build_mineru_client(model_dir)
    from mineru_vl_utils.post_process import json2md
    page_count = 0
    pages = iter_page_images(input_path)
    try:
        for index, image in enumerate(pages):
            start = perf_counter()
            progress.emit(stage='ocr', pages_done=index, pages_total=total, detail='reading_pages')
            blocks = client.two_step_extract(image)
            prefix = output_dir / f"page_{index + 1:04d}"
            raw = {"model": MODEL_ID, "input_path": str(input_path), "page_index": index, "blocks": blocks}
            prefix.with_suffix(".json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            prefix.with_suffix(".md").write_text(json2md(blocks), encoding="utf-8")
            page_count += 1
            progress.emit(stage='ocr', pages_done=page_count, pages_total=total, detail='reading_pages')
            print(f"[MinerU] Page {page_count} saved ({perf_counter() - start:.1f}s)", file=sys.stderr, flush=True)
    finally:
        if hasattr(pages, "close"):
            pages.close()
    return page_count


def main():
    parser = argparse.ArgumentParser(description="Offline MinerU 2.5 Pro document scanner")
    parser.add_argument("file_path", help="Local image or PDF")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--model-dir", default=os.environ.get("HERMES_MINERU_MODEL_DIR", str(DEFAULT_MODEL_DIR)))
    parser.add_argument("--text-only", action="store_true", help="Return text and paths without embedding raw JSON")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    input_path = Path(args.file_path).expanduser().resolve()
    if not input_path.exists():
        send_result({"success": False, "error": "FILE_NOT_FOUND", "file_path": str(input_path)})
        raise SystemExit(1)
    if not input_path.is_file():
        send_result({"success": False, "error": "NOT_A_FILE", "file_path": str(input_path)})
        raise SystemExit(1)
    if input_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        send_result({"success": False, "error": "UNSUPPORTED_FILE_TYPE", "allowed_extensions": sorted(ALLOWED_EXTENSIONS)})
        raise SystemExit(1)
    output_dir = Path(args.output_dir).expanduser().resolve() / f"{input_path.stem}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    start = perf_counter()
    try:
        output_dir.mkdir(parents=True)
        page_count = run_mineru(input_path, output_dir, args.model_dir)
        json_files = [str(p) for p in sorted(output_dir.glob("*.json"), key=page_sort_key)]
        markdown_files = [str(p) for p in sorted(output_dir.glob("*.md"), key=page_sort_key)]
        ocr_text = read_markdown_files(markdown_files)
        if not ocr_text:
            raise ValueError("OCR_TEXT_EMPTY")
        raw = {} if args.text_only else {"ocr_json": read_json_files(json_files)}
    except Exception as exc:
        send_result({"success": False, "error": "MINERU_OCR_ERROR", "message": str(exc),
                     "input_file": str(input_path), "output_dir": str(output_dir)})
        raise SystemExit(1)
    send_result({"success": True, "engine": "mineru", "model": MODEL_ID,
                 "input_file": str(input_path), "file_name": input_path.name,
                 "file_extension": input_path.suffix.lower(), "output_dir": str(output_dir),
                 "page_count": page_count, "elapsed_seconds": round(perf_counter() - start, 3),
                 "ocr_text": ocr_text, "json_files": json_files, "markdown_files": markdown_files, **raw})


if __name__ == "__main__":
    main()
