import json
import os
import subprocess
from pathlib import Path


def _result(data):
    return json.dumps(data, ensure_ascii=False)


def _child_env(project_dir):
    env = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(name, None)
    env["PATH"] = str(project_dir / ".venv" / "Scripts") + os.pathsep + env.get("PATH", "")
    return env


def scan_document_ocr(args: dict, **kwargs) -> str:
    try:
        file_path = str(args.get("file_path", "")).strip()

        if not file_path:
            return _result({
                "success": False,
                "error": "NO_FILE_PATH"
            })

        # Hilangkan quote jika ada
        file_path = file_path.strip('"').strip("'")

        input_path = Path(file_path).expanduser().resolve()

        if not input_path.exists():
            return _result({
                "success": False,
                "error": "FILE_NOT_FOUND",
                "file_path": str(input_path)
            })

        if not input_path.is_file():
            return _result({
                "success": False,
                "error": "NOT_A_FILE",
                "file_path": str(input_path)
            })

        project_path = os.environ.get("HERMES_SCANNER_PROJECT", "").strip()

        if not project_path:
            return _result({
                "success": False,
                "error": "HERMES_SCANNER_PROJECT_NOT_SET"
            })

        project_dir = Path(project_path).expanduser().resolve()

        python_exe = (
            project_dir
            / ".venv"
            / "Scripts"
            / "python.exe"
        )

        runner = project_dir / "ocr_runner.py"

        if not python_exe.exists():
            return _result({
                "success": False,
                "error": "OCR_PYTHON_NOT_FOUND",
                "path": str(python_exe)
            })

        if not runner.exists():
            return _result({
                "success": False,
                "error": "OCR_RUNNER_NOT_FOUND",
                "path": str(runner)
            })

        child_env = _child_env(project_dir)

        timeout = int(os.environ.get("HERMES_OCR_TIMEOUT_SECONDS", "7200"))
        if timeout <= 0:
            raise ValueError("HERMES_OCR_TIMEOUT_SECONDS harus lebih dari nol")
        process = subprocess.run(
            [
                str(python_exe),
                str(runner),
                str(input_path),
                "--text-only",
            ],
            cwd=str(project_dir),
            env=child_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False
        )

        marker = "HERMES_OCR_RESULT="
        result_data = None

        for line in reversed(process.stdout.splitlines()):
            if line.startswith(marker):
                result_data = line[len(marker):]
                break

        if result_data is None:
            return _result({
                "success": False,
                "error": "OCR_RESULT_NOT_FOUND",
                "return_code": process.returncode,
                "stdout": process.stdout[-3000:],
                "stderr": process.stderr[-3000:]
            })

        parsed = json.loads(result_data)

        parsed["return_code"] = process.returncode

        if process.returncode != 0:
            parsed["stderr"] = process.stderr[-3000:]

        if parsed.get("success"):
            parsed["instruction"] = (
                "OCR sudah selesai. Gunakan 'ocr_text' untuk review CV/KAK/lampiran. "
                "JSON layout lengkap tersedia di 'json_files' bila diperlukan."
            )

        return _result(parsed)

    except subprocess.TimeoutExpired:
        return _result({
            "success": False,
            "error": "OCR_TIMEOUT"
        })

    except Exception as exc:
        return _result({
            "success": False,
            "error": "OCR_PLUGIN_ERROR",
            "message": str(exc)
        })


def export_document(args: dict, **kwargs) -> str:
    try:
        template_id = str(args.get("template", "")).strip()
        payload = args.get("payload")
        output_path = str(args.get("output_path", "")).strip().strip('"').strip("'")

        if not template_id or not isinstance(payload, dict) or not output_path:
            return _result({
                "success": False,
                "error": "INVALID_EXPORT_ARGUMENTS"
            })

        project_path = os.environ.get("HERMES_SCANNER_PROJECT", "").strip()
        if not project_path:
            return _result({
                "success": False,
                "error": "HERMES_SCANNER_PROJECT_NOT_SET"
            })

        project_dir = Path(project_path).expanduser().resolve()
        python_exe = project_dir / ".venv" / "Scripts" / "python.exe"
        exporter = project_dir / "exporter.py"

        if not python_exe.exists() or not exporter.exists():
            return _result({
                "success": False,
                "error": "EXPORT_RUNTIME_NOT_FOUND"
            })

        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".xlsx":
            return _result({
                "success": False,
                "error": "OUTPUT_MUST_BE_XLSX"
            })

        child_env = _child_env(project_dir)

        process = subprocess.run(
            [
                str(python_exe),
                str(exporter),
                "--template", template_id,
                "--payload-json", "-",
                "--output", str(output),
            ],
            cwd=str(project_dir),
            env=child_env,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            shell=False,
        )

        marker = "HERMES_EXPORT_RESULT="
        for line in reversed(process.stdout.splitlines()):
            if line.startswith(marker):
                return line[len(marker):]

        return _result({
            "success": False,
            "error": "EXPORT_RESULT_NOT_FOUND",
            "return_code": process.returncode,
            "stdout": process.stdout[-3000:],
            "stderr": process.stderr[-3000:],
        })

    except subprocess.TimeoutExpired:
        return _result({
            "success": False,
            "error": "EXPORT_TIMEOUT"
        })

    except Exception as exc:
        return _result({
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc)
        })


def export_cv_report(args: dict, **kwargs) -> str:
    try:
        payload = args.get("payload")
        output_path = str(args.get("output_path", "")).strip().strip('"').strip("'")
        if not isinstance(payload, dict) or not output_path:
            return _result({"success": False, "error": "INVALID_CV_REPORT_ARGUMENTS"})

        project_path = os.environ.get("HERMES_SCANNER_PROJECT", "").strip()
        if not project_path:
            return _result({"success": False, "error": "HERMES_SCANNER_PROJECT_NOT_SET"})

        project_dir = Path(project_path).expanduser().resolve()
        python_exe = project_dir / ".venv" / "Scripts" / "python.exe"
        renderer = project_dir / "cv_report.py"
        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".docx":
            return _result({"success": False, "error": "OUTPUT_MUST_BE_DOCX"})
        if not python_exe.exists() or not renderer.exists():
            return _result({"success": False, "error": "CV_REPORT_RUNTIME_NOT_FOUND"})

        child_env = _child_env(project_dir)

        process = subprocess.run(
            [str(python_exe), str(renderer), "--payload-json", "-", "--output", str(output)],
            cwd=str(project_dir),
            env=child_env,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            shell=False,
        )
        marker = "HERMES_CV_REPORT_RESULT="
        for line in reversed(process.stdout.splitlines()):
            if line.startswith(marker):
                return line[len(marker):]
        return _result({
            "success": False,
            "error": "CV_REPORT_RESULT_NOT_FOUND",
            "return_code": process.returncode,
            "stdout": process.stdout[-3000:],
            "stderr": process.stderr[-3000:],
        })
    except subprocess.TimeoutExpired:
        return _result({"success": False, "error": "CV_REPORT_TIMEOUT"})
    except Exception as exc:
        return _result({"success": False, "error": type(exc).__name__, "message": str(exc)})
