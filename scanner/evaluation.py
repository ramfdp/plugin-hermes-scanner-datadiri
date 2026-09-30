"""Evaluation contract for Scanner Data Diri v0.5.

This module deliberately defines structure before policy. The fifteen KAK audit
criteria are registered here so later evaluators can implement them one by one
without inventing incompatible field names or status vocabularies. v0.5.0 does
not yet turn the catalog into an automated hiring decision.
"""
import copy
import re

EVALUATION_SCHEMA_VERSION = 2
AUDIT_STATUSES = {"memenuhi", "tidak_memenuhi", "perlu_klarifikasi"}

AUDIT_CRITERIA = (
    {"number": 1, "code": "position_experience_match", "label": "Kesesuaian posisi yang diusulkan dengan pengalaman"},
    {"number": 2, "code": "project_kak_match", "label": "Kesesuaian judul/jenis proyek dengan persyaratan KAK"},
    {"number": 3, "code": "organization_role_match", "label": "Kesesuaian pemberi kerja, konsultan, kontraktor, atau instansi yang diwakili"},
    {"number": 4, "code": "project_period_accuracy", "label": "Ketepatan periode/waktu pelaksanaan proyek"},
    {"number": 5, "code": "experience_duration_match", "label": "Kesesuaian durasi pengalaman dengan syarat KAK"},
    {"number": 6, "code": "responsibility_position_match", "label": "Kesesuaian uraian tugas dengan posisi pada proyek"},
    {"number": 7, "code": "education_major_match", "label": "Kesesuaian pendidikan dan jurusan"},
    {"number": 8, "code": "certificate_kak_validity", "label": "Kesesuaian SKK/SKA/sertifikasi dan masa berlakunya"},
    {"number": 9, "code": "identity_consistency", "label": "Konsistensi nama proyek, perusahaan, jabatan, dan periode"},
    {"number": 10, "code": "project_overlap", "label": "Pengecekan pengalaman proyek yang tumpang tindih"},
    {"number": 11, "code": "project_duplicate", "label": "Pengecekan duplikasi proyek/pengalaman"},
    {"number": 12, "code": "technical_competency_match", "label": "Kesesuaian kompetensi teknis dengan kebutuhan KAK"},
    {"number": 13, "code": "cv_supporting_document_match", "label": "Kesesuaian CV dengan dokumen pendukung"},
    {"number": 14, "code": "data_anomaly", "label": "Anomali/kesalahan data yang perlu klarifikasi atau revisi"},
    {"number": 15, "code": "kak_conclusion", "label": "Kesimpulan pemenuhan KAK"},
)
AUDIT_CODES = {item["code"] for item in AUDIT_CRITERIA}


def criterion_catalog():
    return copy.deepcopy(list(AUDIT_CRITERIA))


def evaluation_metadata():
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "criteria_count": len(AUDIT_CRITERIA),
        "criteria": criterion_catalog(),
        "note": "Kontrak evaluasi tersedia; implementasi pemeriksaan 1-15 dilakukan bertahap dan tetap memerlukan bukti.",
    }


def assign_experience_ids(history):
    """Give each experience a deterministic snapshot-local ID without rewriting claims."""
    seen = set()
    for index, row in enumerate(history, 1):
        value = row.get("id")
        if value in (None, ""):
            value = f"E{index:03d}"
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value):
            raise ValueError("employment_history.id hanya huruf, angka, _, - maksimal 40 karakter")
        if value in seen:
            raise ValueError("employment_history.id duplikat")
        row["id"] = value
        seen.add(value)
    return history


def validate_audit_checks(value):
    """Validate the v2 audit envelope without pretending the checks are implemented yet."""
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("audit_checks harus array object")
    rows = copy.deepcopy(value)
    seen = set()
    for row in rows:
        code = row.get("code")
        if code not in AUDIT_CODES:
            raise ValueError("audit_checks.code tidak dikenal")
        if code in seen:
            raise ValueError("audit_checks.code duplikat")
        seen.add(code)
        applicable = row.get("applicable", True)
        if not isinstance(applicable, bool):
            raise ValueError("audit_checks.applicable harus boolean")
        row["applicable"] = applicable
        if applicable:
            if row.get("status") not in AUDIT_STATUSES:
                raise ValueError("audit_checks.status harus memenuhi/tidak_memenuhi/perlu_klarifikasi")
            for key in ("finding", "analysis"):
                if not isinstance(row.get(key), str) or not row[key].strip():
                    raise ValueError(f"audit_checks.{key} wajib berupa teks")
            if row["status"] == "perlu_klarifikasi" and (not isinstance(row.get("clarification"), str) or not row["clarification"].strip()):
                raise ValueError("audit_checks.clarification wajib untuk status perlu_klarifikasi")
        else:
            row["status"] = None
    return rows
