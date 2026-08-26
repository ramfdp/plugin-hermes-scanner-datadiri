import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from paddleocr import PaddleOCRVL


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".pdf",
}


def send_result(data: dict):
    print(
        "HERMES_OCR_RESULT="
        + json.dumps(
            data,
            ensure_ascii=False,
        )
    )


def read_markdown_files(markdown_files):
    contents = []

    for index, file_path in enumerate(markdown_files, start=1):
        path = Path(file_path)

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

            if len(markdown_files) > 1:
                contents.append(
                    f"\n--- PAGE {index} ---\n{text}"
                )
            else:
                contents.append(text)

        except Exception as exc:
            contents.append(
                f"[Gagal membaca {path.name}: {exc}]"
            )

    return "\n".join(contents).strip()


def read_json_files(json_files):
    return [
        json.loads(Path(file_path).read_text(encoding="utf-8-sig"))
        for file_path in json_files
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Local PaddleOCR-VL document scanner"
    )

    parser.add_argument(
        "file_path",
        help="Path file gambar atau PDF yang akan diproses",
    )

    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory",
    )

    args = parser.parse_args()

    # ==========================================================
    # INPUT
    # ==========================================================

    input_path = (
        Path(args.file_path)
        .expanduser()
        .resolve()
    )

    if not input_path.exists():
        send_result(
            {
                "success": False,
                "error": "FILE_NOT_FOUND",
                "file_path": str(input_path),
            }
        )
        sys.exit(1)

    if not input_path.is_file():
        send_result(
            {
                "success": False,
                "error": "NOT_A_FILE",
                "file_path": str(input_path),
            }
        )
        sys.exit(1)

    extension = input_path.suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        send_result(
            {
                "success": False,
                "error": "UNSUPPORTED_FILE_TYPE",
                "extension": extension,
                "allowed_extensions": sorted(
                    ALLOWED_EXTENSIONS
                ),
            }
        )
        sys.exit(1)

    # ==========================================================
    # OUTPUT DIRECTORY
    # ==========================================================

    if args.output_dir:
        output_root = (
            Path(args.output_dir)
            .expanduser()
            .resolve()
        )
    else:
        output_root = DEFAULT_OUTPUT_DIR

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_dir = (
        output_root
        / f"{input_path.stem}_{timestamp}"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ==========================================================
    # PADDLE OCR
    # ==========================================================

    try:
        pipeline = PaddleOCRVL(
            pipeline_version="v1.6"
        )

        results = pipeline.predict(
            str(input_path)
        )

        page_count = 0

        for res in results:
            page_count += 1

            res.save_to_json(
                save_path=output_dir
            )

            res.save_to_markdown(
                save_path=output_dir
            )

    except Exception as exc:
        send_result(
            {
                "success": False,
                "error": "PADDLE_OCR_ERROR",
                "message": str(exc),
                "input_file": str(input_path),
            }
        )
        sys.exit(1)

    # ==========================================================
    # FIND GENERATED FILES
    # ==========================================================

    json_paths = sorted(
        output_dir.rglob("*.json")
    )

    markdown_paths = sorted(
        output_dir.rglob("*.md")
    )

    json_files = [
        str(path)
        for path in json_paths
    ]

    markdown_files = [
        str(path)
        for path in markdown_paths
    ]

    # ==========================================================
    # READ OCR CONTENT
    # ==========================================================

    ocr_text = read_markdown_files(
        markdown_files
    )

    try:
        ocr_json = read_json_files(json_files)
    except (OSError, json.JSONDecodeError) as exc:
        send_result(
            {
                "success": False,
                "error": "OCR_JSON_INVALID",
                "message": str(exc),
                "input_file": str(input_path),
                "output_dir": str(output_dir),
                "json_files": json_files,
            }
        )
        sys.exit(1)

    if not ocr_text:
        send_result(
            {
                "success": False,
                "error": "OCR_TEXT_EMPTY",
                "input_file": str(input_path),
                "output_dir": str(output_dir),
                "json_files": json_files,
                "markdown_files": markdown_files,
            }
        )
        sys.exit(1)

    # ==========================================================
    # RESPONSE TO HERMES
    # ==========================================================

    send_result(
        {
            "success": True,
            "input_file": str(input_path),
            "file_name": input_path.name,
            "file_extension": extension,
            "output_dir": str(output_dir),
            "page_count": page_count,

            # Yang paling penting:
            "ocr_text": ocr_text,

            # Data mentah untuk dipetakan Hermes ke payload exporter.
            "ocr_json": ocr_json,

            # Tetap kita simpan untuk audit/debug.
            "json_files": json_files,
            "markdown_files": markdown_files,
        }
    )


if __name__ == "__main__":
    main()
