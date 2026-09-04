import json
import os
import sys
import time
from pathlib import Path

import fitz
from paddleocr import PaddleOCR

PDF_PATH = Path(r"C:\Users\ASPIRE 7\Downloads\Scan CV TA Jawa 1 ttd lengkap.pdf")
OUT_DIR = Path(r"C:\hscan\cv_extract_work")
IMG_DIR = OUT_DIR / "page_images"
TEXT_JSONL = OUT_DIR / "ocr_pages.jsonl"
PROGRESS = OUT_DIR / "progress.txt"

OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

# Resume support: skip pages already in jsonl
seen = set()
if TEXT_JSONL.exists():
    with TEXT_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                seen.add(json.loads(line)["page"])
            except Exception:
                pass

ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
)

doc = fitz.open(str(PDF_PATH))
total = len(doc)
start = time.time()

with TEXT_JSONL.open("a", encoding="utf-8") as out:
    for idx in range(total):
        page_no = idx + 1
        if page_no in seen:
            continue
        page = doc[idx]
        # Render at moderate resolution; enough for CV fields, faster than VL.
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        img_path = IMG_DIR / f"page_{page_no:04d}.png"
        pix.save(str(img_path))
        try:
            results = ocr.predict(str(img_path))
            texts = []
            scores = []
            boxes = []
            for res in results:
                d = dict(res)
                texts.extend(d.get("rec_texts") or [])
                scores.extend([float(x) for x in (d.get("rec_scores") or [])])
                rb = d.get("rec_boxes")
                if rb is not None:
                    try:
                        boxes.extend(rb.tolist())
                    except Exception:
                        pass
            rec = {"page": page_no, "text": "\n".join(texts), "texts": texts, "scores": scores, "boxes": boxes}
        except Exception as e:
            rec = {"page": page_no, "error": type(e).__name__, "message": str(e), "text": "", "texts": []}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        if page_no % 5 == 0 or page_no == total:
            elapsed = time.time() - start
            PROGRESS.write_text(f"page {page_no}/{total}; elapsed {elapsed:.1f}s\n", encoding="utf-8")
            print(f"page {page_no}/{total}; elapsed {elapsed:.1f}s", flush=True)

print(f"OCR_JSONL={TEXT_JSONL}")
