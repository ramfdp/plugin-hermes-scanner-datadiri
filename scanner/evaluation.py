"""Deterministic evaluation helpers for Scanner Data Diri.

The module owns facts that can be computed safely from structured evidence:
period validity, consistency against supporting facts, overlapping experience,
and duplicate/near-duplicate experience. Semantic KAK matching remains a later
layer and is not guessed here.
"""
import copy
import re
import unicodedata
from calendar import monthrange
from datetime import date
from difflib import SequenceMatcher

EVALUATION_SCHEMA_VERSION = 3
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
FACT_AUDIT_CODES = {
    "project_period_accuracy",
    "identity_consistency",
    "project_overlap",
    "project_duplicate",
}
FACT_FIELDS = ("project", "employer", "role", "start_date", "end_date")


def criterion_catalog():
    return copy.deepcopy(list(AUDIT_CRITERIA))


def evaluation_metadata():
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "criteria_count": len(AUDIT_CRITERIA),
        "criteria": criterion_catalog(),
        "implemented_codes": sorted(FACT_AUDIT_CODES),
        "note": "Pemeriksaan fakta #4/#9/#10/#11 dihitung server-side; kriteria lain diimplementasikan bertahap.",
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
    """Validate audit envelopes. Server-computed codes are rejected elsewhere."""
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
            if row["status"] == "perlu_klarifikasi" and (
                not isinstance(row.get("clarification"), str) or not row["clarification"].strip()
            ):
                raise ValueError("audit_checks.clarification wajib untuk status perlu_klarifikasi")
        else:
            row["status"] = None
    return rows


def canonical_text(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def partial_date(value):
    """Return bounded calendar meaning without inventing precision."""
    if not isinstance(value, str) or not value.strip():
        return {"valid": False, "raw": value, "reason": "tanggal kosong"}
    raw = value.strip()
    try:
        if re.fullmatch(r"\d{4}", raw):
            year = int(raw)
            return {
                "valid": True, "raw": raw, "precision": "year",
                "first": date(year, 1, 1), "last": date(year, 12, 31),
            }
        if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", raw):
            year, month = map(int, raw.split("-"))
            return {
                "valid": True, "raw": raw, "precision": "month",
                "first": date(year, month, 1),
                "last": date(year, month, monthrange(year, month)[1]),
            }
        if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])-([0-2]\d|3[01])", raw):
            exact = date.fromisoformat(raw)
            return {"valid": True, "raw": raw, "precision": "day", "first": exact, "last": exact}
    except ValueError:
        pass
    return {"valid": False, "raw": raw, "reason": "format/tanggal tidak valid"}


def experience_interval(job):
    start = partial_date(job.get("start_date"))
    end = partial_date(job.get("end_date"))
    if not start["valid"] or not end["valid"]:
        return {
            "valid": False, "experience_id": job.get("id"),
            "start": start, "end": end,
            "reason": "periode belum memiliki tanggal mulai/akhir yang valid",
        }
    if start["first"] > end["last"]:
        return {
            "valid": False, "experience_id": job.get("id"),
            "start": start, "end": end,
            "reason": "tanggal mulai berada setelah tanggal akhir",
        }
    return {
        "valid": True, "experience_id": job.get("id"),
        "start": start, "end": end,
        "first": start["first"], "last": end["last"],
        "approximate": start["precision"] != "day" or end["precision"] != "day",
    }


def date_values_compatible(left, right):
    a, b = partial_date(left), partial_date(right)
    if not a["valid"] or not b["valid"]:
        return False
    return max(a["first"], b["first"]) <= min(a["last"], b["last"])


def _unique_refs(values):
    result, seen = [], set()
    for ref in values:
        if not isinstance(ref, dict):
            continue
        key = (ref.get("document_id"), ref.get("page"), ref.get("quote"))
        if key in seen:
            continue
        seen.add(key)
        result.append(copy.deepcopy(ref))
    return result


def _job_refs(job):
    refs = [*job.get("source_refs", []), *job.get("supporting_refs", [])]
    for fact in job.get("supporting_facts", []):
        refs.extend(fact.get("source_refs", []))
    return refs


def _refs_for(history, ids=None):
    selected = set(ids or [])
    refs = []
    for job in history:
        if selected and job.get("id") not in selected:
            continue
        refs.extend(_job_refs(job))
    return _unique_refs(refs)


def _check(code, status, finding, analysis, refs, clarification=""):
    row = {
        "code": code,
        "applicable": True,
        "status": status,
        "finding": finding,
        "analysis": analysis,
        "source_refs": _unique_refs(refs),
        "kak_refs": [],
        "computed": True,
    }
    if status == "perlu_klarifikasi":
        row["clarification"] = clarification or "Periksa kembali dokumen sumber dan konfirmasi data yang berbeda atau belum didukung."
    return row


def _not_applicable(code, finding):
    return {
        "code": code,
        "applicable": False,
        "status": None,
        "finding": finding,
        "analysis": finding,
        "source_refs": [],
        "kak_refs": [],
        "computed": True,
    }


def _supporting_facts(job):
    value = job.get("supporting_facts", [])
    return value if isinstance(value, list) else []


def evaluate_period_accuracy(history, as_of):
    entries, issues = [], []
    if not history:
        return {
            "entries": [],
            "issues": ["Tidak ada riwayat pengalaman untuk memeriksa periode proyek."],
            "check": _check(
                "project_period_accuracy", "perlu_klarifikasi",
                "Periode proyek belum dapat diperiksa karena riwayat pengalaman kosong.",
                "Tidak ada tanggal mulai/akhir pengalaman yang dapat diuji terhadap tanggal acuan atau dokumen pendukung.",
                [], "Lengkapi riwayat pengalaman beserta periode dan bukti pendukung.",
            ),
        }

    all_supported = True
    for job in history:
        interval = experience_interval(job)
        entry = {
            "experience_id": job["id"],
            "start_date": job.get("start_date", ""),
            "end_date": job.get("end_date", ""),
            "valid": interval["valid"],
            "support": [],
        }
        if not interval["valid"]:
            issues.append({"experience_id": job["id"], "type": "invalid_period", "detail": interval["reason"]})
            all_supported = False
            entries.append(entry)
            continue
        if interval["first"] > as_of:
            issues.append({"experience_id": job["id"], "type": "future_start",
                           "detail": "Tanggal mulai berada setelah tanggal acuan pemeriksaan."})
        if interval["last"] > as_of:
            issues.append({"experience_id": job["id"], "type": "extends_beyond_assessment",
                           "detail": "Tanggal akhir melewati tanggal acuan; pengalaman setelah tanggal acuan belum boleh dianggap telah diperoleh."})

        facts = _supporting_facts(job)
        period_facts = [fact for fact in facts if fact.get("start_date") or fact.get("end_date")]
        if not period_facts:
            all_supported = False
            issues.append({"experience_id": job["id"], "type": "period_not_supported",
                           "detail": "Belum ada supporting_facts yang memuat periode proyek."})
        complete_support = False
        for fact in period_facts:
            result = {"source_refs": copy.deepcopy(fact.get("source_refs", [])), "matches": {}}
            for field in ("start_date", "end_date"):
                value = fact.get(field)
                if value:
                    result["matches"][field] = date_values_compatible(job.get(field), value)
                    if not result["matches"][field]:
                        issues.append({"experience_id": job["id"], "type": "period_conflict",
                                       "field": field, "cv_value": job.get(field), "support_value": value})
            if fact.get("start_date") and fact.get("end_date") and all(result["matches"].values()):
                complete_support = True
            entry["support"].append(result)
        if period_facts and not complete_support:
            all_supported = False
        entries.append(entry)

    status = "memenuhi" if not issues and all_supported else "perlu_klarifikasi"
    if status == "memenuhi":
        finding = "Seluruh periode pengalaman terbaca valid dan konsisten dengan periode pada dokumen pendukung."
        clarification = ""
    else:
        finding = f"Ditemukan {len(issues)} isu/keterbatasan pada pemeriksaan periode pengalaman."
        clarification = "Konfirmasi periode yang konflik, melewati tanggal acuan, tidak presisi, atau belum memiliki bukti periode pendukung."
    return {
        "entries": entries,
        "issues": issues,
        "check": _check(
            "project_period_accuracy", status, finding,
            "Periode diuji menggunakan tanggal sebagaimana tertulis. YYYY/ YYYY-MM diperlakukan sebagai rentang kalender sesuai presisinya untuk perbandingan, tanpa mengubah nilai asli.",
            _refs_for(history), clarification,
        ),
    }


def _field_matches(field, claimed, supported):
    if field in {"start_date", "end_date"}:
        return date_values_compatible(claimed, supported)
    return bool(canonical_text(claimed)) and canonical_text(claimed) == canonical_text(supported)


def evaluate_consistency(history):
    conflicts, missing, entries = [], [], []
    if not history:
        return {
            "entries": [], "conflicts": [], "missing": ["employment_history"],
            "check": _check(
                "identity_consistency", "perlu_klarifikasi",
                "Konsistensi proyek/perusahaan/jabatan/periode belum dapat diperiksa karena riwayat pengalaman kosong.",
                "Pemeriksaan membutuhkan klaim pengalaman dan fakta dari dokumen pendukung.",
                [], "Lengkapi riwayat pengalaman dan dokumen pendukung.",
            ),
        }

    for job in history:
        facts = _supporting_facts(job)
        row = {"experience_id": job["id"], "comparisons": []}
        if not facts:
            missing.append({"experience_id": job["id"], "field": "supporting_facts"})
        supported_fields = set()
        for fact in facts:
            comparison = {"source_refs": copy.deepcopy(fact.get("source_refs", [])), "fields": {}}
            for field in FACT_FIELDS:
                if not fact.get(field):
                    continue
                supported_fields.add(field)
                match = _field_matches(field, job.get(field), fact.get(field))
                comparison["fields"][field] = {
                    "match": match, "cv_value": job.get(field, ""), "support_value": fact.get(field, ""),
                }
                if not match:
                    conflicts.append({
                        "experience_id": job["id"], "field": field,
                        "cv_value": job.get(field, ""), "support_value": fact.get(field, ""),
                    })
            row["comparisons"].append(comparison)
        for field in FACT_FIELDS:
            if field not in supported_fields:
                missing.append({"experience_id": job["id"], "field": field})
        entries.append(row)

    status = "memenuhi" if not conflicts and not missing else "perlu_klarifikasi"
    if status == "memenuhi":
        finding = "Nama proyek, perusahaan, jabatan, dan periode konsisten dengan fakta dokumen pendukung."
        clarification = ""
    else:
        finding = f"Ditemukan {len(conflicts)} konflik dan {len(missing)} field yang belum dapat dicross-check."
        clarification = "Konfirmasi nilai yang berbeda dan lengkapi dokumen pendukung untuk field yang belum dapat dibandingkan."
    return {
        "entries": entries,
        "conflicts": conflicts,
        "missing": missing,
        "check": _check(
            "identity_consistency", status, finding,
            "Perbandingan teks bersifat normalisasi ketat (kapitalisasi, tanda baca, spasi); nama berbeda tidak disamakan dengan tebakan alias. Tanggal dibandingkan sesuai presisi yang tersedia.",
            _refs_for(history), clarification,
        ),
    }


def detect_overlaps(history):
    pairs, uncertain = [], []
    if not history:
        return {
            "pairs": [], "uncertain_experience_ids": [],
            "check": _not_applicable("project_overlap", "Tidak ada riwayat pengalaman yang dapat dibandingkan untuk overlap."),
        }
    intervals = {job["id"]: experience_interval(job) for job in history}
    for job in history:
        if not intervals[job["id"]]["valid"]:
            uncertain.append(job["id"])
    for index, left in enumerate(history):
        a = intervals[left["id"]]
        if not a["valid"]:
            continue
        for right in history[index + 1:]:
            b = intervals[right["id"]]
            if not b["valid"]:
                continue
            first, last = max(a["first"], b["first"]), min(a["last"], b["last"])
            if first <= last:
                pairs.append({
                    "left_id": left["id"], "right_id": right["id"],
                    "overlap_start": first.isoformat(), "overlap_end": last.isoformat(),
                    "calendar_days": (last - first).days + 1,
                    "precision": "exact_day" if not a["approximate"] and not b["approximate"] else "calendar_range_from_partial_dates",
                })

    if pairs or uncertain:
        finding = f"Ditemukan {len(pairs)} pasangan pengalaman yang bertumpang tindih."
        if uncertain:
            finding += f" {len(uncertain)} pengalaman tidak memiliki periode yang cukup valid untuk dibandingkan."
        check = _check(
            "project_overlap", "perlu_klarifikasi", finding,
            "Overlap adalah fakta kronologi, bukan otomatis pelanggaran. Reviewer perlu memastikan apakah pekerjaan memang berjalan bersamaan dan bagaimana KAK memperlakukan periode tersebut.",
            _refs_for(history, {item for pair in pairs for item in (pair["left_id"], pair["right_id"])} | set(uncertain)),
            "Konfirmasi proyek yang berjalan bersamaan dan periode yang belum valid; jangan menghapus pengalaman hanya karena overlap.",
        )
    else:
        check = _check(
            "project_overlap", "memenuhi",
            "Tidak ditemukan periode pengalaman yang bertumpang tindih.",
            "Seluruh pasangan pengalaman dengan periode valid dibandingkan sebagai rentang kalender inklusif.",
            _refs_for(history),
        )
    return {"pairs": pairs, "uncertain_experience_ids": uncertain, "check": check}


def _exact_signature(job):
    return (
        canonical_text(job.get("project")),
        canonical_text(job.get("employer")),
        canonical_text(job.get("role")),
        str(job.get("start_date", "")).strip(),
        str(job.get("end_date", "")).strip(),
    )


def detect_duplicates(history):
    pairs, insufficient = [], []
    if not history:
        return {
            "pairs": [], "insufficient_experience_ids": [],
            "check": _not_applicable("project_duplicate", "Tidak ada riwayat pengalaman yang dapat dibandingkan untuk duplikasi."),
        }

    intervals = {job["id"]: experience_interval(job) for job in history}
    for job in history:
        if not canonical_text(job.get("project")):
            insufficient.append(job["id"])

    for index, left in enumerate(history):
        for right in history[index + 1:]:
            if _exact_signature(left) == _exact_signature(right) and canonical_text(left.get("project")):
                pairs.append({
                    "left_id": left["id"], "right_id": right["id"], "type": "exact",
                    "project_similarity": 1.0,
                })
                continue
            project_a, project_b = canonical_text(left.get("project")), canonical_text(right.get("project"))
            employer_same = canonical_text(left.get("employer")) == canonical_text(right.get("employer")) != ""
            role_same = canonical_text(left.get("role")) == canonical_text(right.get("role")) != ""
            if not project_a or not project_b or not employer_same or not role_same:
                continue
            similarity = SequenceMatcher(None, project_a, project_b).ratio()
            a, b = intervals[left["id"]], intervals[right["id"]]
            overlaps = a["valid"] and b["valid"] and max(a["first"], b["first"]) <= min(a["last"], b["last"])
            if similarity >= 0.92 and overlaps:
                pairs.append({
                    "left_id": left["id"], "right_id": right["id"], "type": "possible",
                    "project_similarity": round(similarity, 4),
                })

    if pairs or (len(history) > 1 and insufficient):
        finding = f"Ditemukan {sum(p['type'] == 'exact' for p in pairs)} duplikasi exact dan {sum(p['type'] == 'possible' for p in pairs)} kandidat duplikasi."
        if insufficient:
            finding += f" {len(insufficient)} pengalaman tidak memiliki nama proyek yang cukup untuk dibandingkan."
        ids = {item for pair in pairs for item in (pair["left_id"], pair["right_id"])} | set(insufficient)
        check = _check(
            "project_duplicate", "perlu_klarifikasi", finding,
            "Duplikasi exact memakai proyek, perusahaan, jabatan, dan periode yang sama setelah normalisasi. Kandidat duplikasi memerlukan perusahaan+jabatan sama, judul proyek sangat mirip, dan periode overlap; kandidat tidak dihapus otomatis.",
            _refs_for(history, ids),
            "Konfirmasi pasangan duplikasi/kandidat duplikasi sebelum pengalaman dipakai dalam perhitungan atau laporan final.",
        )
    else:
        check = _check(
            "project_duplicate", "memenuhi",
            "Tidak ditemukan duplikasi exact maupun kandidat duplikasi pengalaman.",
            "Riwayat dibandingkan menggunakan identitas proyek/perusahaan/jabatan/periode; kemiripan judul saja tidak cukup untuk menyatakan duplikat.",
            _refs_for(history),
        )
    return {"pairs": pairs, "insufficient_experience_ids": insufficient, "check": check}


def evaluate_history_facts(history, as_of):
    """Compute audit checks #4, #9, #10 and #11 from validated structured history."""
    period = evaluate_period_accuracy(history, as_of)
    consistency = evaluate_consistency(history)
    overlap = detect_overlaps(history)
    duplicate = detect_duplicates(history)
    checks = [period["check"], consistency["check"], overlap["check"], duplicate["check"]]
    order = {item["code"]: item["number"] for item in AUDIT_CRITERIA}
    checks.sort(key=lambda item: order[item["code"]])
    return {
        "method_version": 1,
        "period": {key: value for key, value in period.items() if key != "check"},
        "consistency": {key: value for key, value in consistency.items() if key != "check"},
        "overlaps": {key: value for key, value in overlap.items() if key != "check"},
        "duplicates": {key: value for key, value in duplicate.items() if key != "check"},
        "audit_checks": checks,
    }
