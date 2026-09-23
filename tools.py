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


<<<<<<< HEAD
def _export_result(process, marker, output):
    for line in reversed(process.stdout.splitlines()):
        if line.startswith(marker):
            result = json.loads(line[len(marker):])
            if process.returncode != 0:
                result.update(success=False, error="EXPORT_PROCESS_FAILED",
                              return_code=process.returncode, stderr=process.stderr[-3000:])
            elif result.get("success") and not output.is_file():
                result.update(success=False, error="EXPORT_FILE_NOT_FOUND", output_file=str(output))
            return _result(result)
    return _result({"success": False, "error": "EXPORT_RESULT_NOT_FOUND",
                    "return_code": process.returncode, "stdout": process.stdout[-3000:],
                    "stderr": process.stderr[-3000:]})
=======
def _parse_result(process, prefix):
    marker = f"HERMES_{prefix}_RESULT="
    diagnostics = {
        "return_code": process.returncode,
        "stdout": process.stdout[-3000:],
        "stderr": process.stderr[-3000:],
    }
    for line in reversed(process.stdout.splitlines()):
        if line.startswith(marker):
            try:
                parsed = json.loads(line[len(marker):])
                if not isinstance(parsed, dict) or not isinstance(parsed.get("success"), bool):
                    raise ValueError("Result harus berupa object dengan success boolean")
            except (ValueError, TypeError) as exc:
                return {"success": False, "error": f"{prefix}_INVALID_RESULT",
                        "message": str(exc), **diagnostics}
            parsed["return_code"] = process.returncode
            if process.returncode != 0:
                # A success marker must never hide a failed child process.
                parsed["success"] = False
                if not parsed.get("error"):
                    parsed["error"] = f"{prefix}_PROCESS_FAILED"
                parsed["stderr"] = process.stderr[-3000:]
            return parsed
    return {"success": False, "error": f"{prefix}_RESULT_NOT_FOUND", **diagnostics}


def _run_script(script_name, prefix, arguments, *, payload=None, timeout=120, output=None):
    project_path = os.environ.get("HERMES_SCANNER_PROJECT", "").strip()
    if not project_path:
        return {"success": False, "error": "HERMES_SCANNER_PROJECT_NOT_SET"}
    project_dir = Path(project_path).expanduser().resolve()
    python_exe = project_dir / ".venv" / "Scripts" / "python.exe"
    script = project_dir / script_name
    for path, kind in ((python_exe, "PYTHON"), (script, "RUNNER")):
        if not path.is_file():
            if prefix == "OCR":
                return {"success": False, "error": f"OCR_{kind}_NOT_FOUND", "path": str(path)}
            return {"success": False, "error": f"{prefix}_RUNTIME_NOT_FOUND"}
    try:
        process = subprocess.run(
            [str(python_exe), str(script), *arguments],
            cwd=str(project_dir), env=_child_env(project_dir),
            input=None if payload is None else json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"{prefix}_TIMEOUT"}
    result = _parse_result(process, prefix)
    if result.get("success") and output is not None:
        if not output.is_file() or output.stat().st_size == 0:
            return {"success": False, "error": f"{prefix}_OUTPUT_NOT_FOUND",
                    "output_file": str(output), "return_code": process.returncode}
    return result
>>>>>>> 47b178571b83a89922cbff90af5c0b5f00dff3c2


def scan_document_ocr(args: dict, **kwargs) -> str:
    try:
        file_path = str(args.get("file_path", "")).strip().strip('"').strip("'")
        if not file_path:
            return _result({"success": False, "error": "NO_FILE_PATH"})
        input_path = Path(file_path).expanduser().resolve()
        if not input_path.exists():
            return _result({"success": False, "error": "FILE_NOT_FOUND", "file_path": str(input_path)})
        if not input_path.is_file():
            return _result({"success": False, "error": "NOT_A_FILE", "file_path": str(input_path)})
        timeout = int(os.environ.get("HERMES_OCR_TIMEOUT_SECONDS", "7200"))
        if timeout <= 0:
            raise ValueError("HERMES_OCR_TIMEOUT_SECONDS harus lebih dari nol")
<<<<<<< HEAD
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
            parsed["success"] = False
            parsed["stderr"] = process.stderr[-3000:]

        if parsed.get("success"):
            parsed["instruction"] = (
=======
        result = _run_script("ocr_runner.py", "OCR", [str(input_path), "--text-only"], timeout=timeout)
        if result.get("success"):
            if not isinstance(result.get("ocr_text"), str) or not result["ocr_text"].strip():
                return _result({"success": False, "error": "OCR_INVALID_RESULT",
                                "message": "Hasil OCR tidak berisi ocr_text"})
            result["instruction"] = (
>>>>>>> 47b178571b83a89922cbff90af5c0b5f00dff3c2
                "OCR sudah selesai. Gunakan 'ocr_text' untuk review CV/KAK/lampiran. "
                "JSON layout lengkap tersedia di 'json_files' bila diperlukan."
            )
        return _result(result)
    except Exception as exc:
        return _result({"success": False, "error": "OCR_PLUGIN_ERROR", "message": str(exc)})


def export_document(args: dict, **kwargs) -> str:
    try:
        template_id = str(args.get("template", "")).strip()
        payload = args.get("payload")
        output_path = str(args.get("output_path", "")).strip().strip('"').strip("'")
        if not template_id or not isinstance(payload, dict) or not output_path:
            return _result({"success": False, "error": "INVALID_EXPORT_ARGUMENTS"})
        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".xlsx":
<<<<<<< HEAD
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

        return _export_result(process, "HERMES_EXPORT_RESULT=", output)

    except subprocess.TimeoutExpired:
        return _result({
            "success": False,
            "error": "EXPORT_TIMEOUT"
        })

=======
            return _result({"success": False, "error": "OUTPUT_MUST_BE_XLSX"})
        return _result(_run_script(
            "exporter.py", "EXPORT",
            ["--template", template_id, "--payload-json", "-", "--output", str(output)],
            payload=payload, output=output,
        ))
>>>>>>> 47b178571b83a89922cbff90af5c0b5f00dff3c2
    except Exception as exc:
        return _result({"success": False, "error": type(exc).__name__, "message": str(exc)})


def export_cv_report(args: dict, **kwargs) -> str:
    try:
        payload = args.get("payload")
        output_path = str(args.get("output_path", "")).strip().strip('"').strip("'")
        if not isinstance(payload, dict) or not output_path:
            return _result({"success": False, "error": "INVALID_CV_REPORT_ARGUMENTS"})
        output = Path(output_path).expanduser().resolve()
        if output.suffix.lower() != ".docx":
            return _result({"success": False, "error": "OUTPUT_MUST_BE_DOCX"})
<<<<<<< HEAD
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
        return _export_result(process, "HERMES_CV_REPORT_RESULT=", output)
    except subprocess.TimeoutExpired:
        return _result({"success": False, "error": "CV_REPORT_TIMEOUT"})
=======
        return _result(_run_script(
            "cv_report.py", "CV_REPORT",
            ["--payload-json", "-", "--output", str(output)],
            payload=payload, output=output,
        ))
>>>>>>> 47b178571b83a89922cbff90af5c0b5f00dff3c2
    except Exception as exc:
        return _result({"success": False, "error": type(exc).__name__, "message": str(exc)})
