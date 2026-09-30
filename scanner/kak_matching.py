"""KAK matching engine for audit criteria #1/#2/#3/#5/#6/#7/#8/#12.

Semantic comparisons are supplied by Hermes as requirement-scoped assessments,
but the backend validates coverage and aggregates them. Duration, education and
certificate checks are computed locally from structured data.
"""
import copy
from .evaluation import (AUDIT_CRITERIA, DETERMINISTIC_MATCH_CODES, KAK_MATCH_CODES,
                         SEMANTIC_MATCH_CODES, canonical_text)
LEVEL_RANK = {
    "sma": 1, "smk": 1,
    "d1": 2, "d2": 3, "d3": 4,
    "d4": 5, "s1": 5,
    "profesi": 6, "s2": 7, "s3": 8,
}


def applicable(requirement, role):
    value = canonical_text(requirement.get("role"))
    return value == "*" or value == canonical_text(role)


def _list_text(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} harus array teks non-kosong")
    return [item.strip() for item in value]


def validate_requirement_extension(requirement, evidence_text):
    """Validate structured KAK fields against the cited KAK text."""
    code = requirement.get("audit_code")
    if code in (None, ""):
        requirement.pop("audit_code", None)
        requirement.pop("parameters", None)
        return requirement
    if code not in KAK_MATCH_CODES:
        raise ValueError("requirements.audit_code hanya mendukung audit #1/#2/#3/#5/#6/#7/#8/#12")
    requirement["audit_code"] = code
    params = requirement.get("parameters", {})
    if not isinstance(params, dict):
        raise ValueError("requirements.parameters harus object")
    allowed = set()
    if code == "experience_duration_match":
        allowed = set()
        if requirement.get("kind") != "experience":
            raise ValueError("experience_duration_match harus requirement kind=experience")
        minimum = requirement.get("minimum_months")
        if type(minimum) is not int or minimum < 0:
            raise ValueError("experience_duration_match memerlukan minimum_months integer >= 0")
    elif code == "education_major_match":
        allowed = {"minimum_level", "accepted_majors"}
        if requirement.get("kind") != "education":
            raise ValueError("education_major_match harus requirement kind=education")
        level = params.get("minimum_level", "")
        if level is not None and not isinstance(level, str):
            raise ValueError("parameters.minimum_level harus string")
        majors = _list_text(params.get("accepted_majors", []), "parameters.accepted_majors")
        if not (isinstance(level, str) and level.strip()) and not majors:
            raise ValueError("education_major_match memerlukan minimum_level dan/atau accepted_majors")
        params["minimum_level"] = level.strip() if isinstance(level, str) else ""
        if params["minimum_level"] and canonical_text(params["minimum_level"]).replace(" ", "") not in LEVEL_RANK:
            raise ValueError("parameters.minimum_level tidak dikenal; gunakan SMA/SMK/D1/D2/D3/D4/S1/Profesi/S2/S3")
        params["accepted_majors"] = majors
    elif code == "certificate_kak_validity":
        allowed = {"schemes", "levels", "issuers", "require_current"}
        if requirement.get("kind") != "certificate":
            raise ValueError("certificate_kak_validity harus requirement kind=certificate")
        for key in ("schemes", "levels", "issuers"):
            params[key] = _list_text(params.get(key, []), f"parameters.{key}")
        if not isinstance(params.get("require_current", True), bool):
            raise ValueError("parameters.require_current harus boolean")
        params["require_current"] = params.get("require_current", True)
    else:
        if code in {
            "position_experience_match", "project_kak_match", "organization_role_match",
            "responsibility_position_match",
        } and requirement.get("kind") not in {"experience", "other"}:
            raise ValueError(f"{code} harus requirement kind=experience/other")
        if code == "technical_competency_match" and requirement.get("kind") not in {"experience", "other"}:
            raise ValueError("technical_competency_match harus requirement kind=experience/other")
        if params:
            raise ValueError(f"{code} tidak memakai parameters pada versi ini")

    extra = set(params) - allowed
    if extra:
        raise ValueError("Parameter requirement tidak dikenal: " + ", ".join(sorted(extra)))

    cited = canonical_text(evidence_text)
    values = []
    if code == "education_major_match":
        if params.get("minimum_level"):
            values.append(params["minimum_level"])
        values.extend(params.get("accepted_majors", []))
    elif code == "certificate_kak_validity":
        for key in ("schemes", "levels", "issuers"):
            values.extend(params.get(key, []))
    for value in values:
        if canonical_text(value) not in cited:
            raise ValueError(f"Parameter KAK '{value}' tidak ditemukan pada kutipan requirement")
    requirement["parameters"] = params
    return requirement


def validate_semantic_assessments(value, requirements, role, history_ids):
    applicable_requirements = {
        req["id"]: req for req in requirements
        if req.get("audit_code") in SEMANTIC_MATCH_CODES and applicable(req, role)
    }
    if value is None:
        value = []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("semantic_assessments harus array object")
    if len(value) != len(applicable_requirements):
        raise ValueError("semantic_assessments harus mencakup tepat semua requirement semantic KAK yang berlaku")
    seen, result = set(), []
    known_ids = set(history_ids)
    for raw in value:
        row = copy.deepcopy(raw)
        req_id = row.get("requirement_id")
        if req_id not in applicable_requirements or req_id in seen:
            raise ValueError("semantic_assessments.requirement_id tidak dikenal/duplikat")
        seen.add(req_id)
        req = applicable_requirements[req_id]
        if row.get("code") not in (None, req["audit_code"]):
            raise ValueError("semantic_assessments.code tidak sesuai requirement")
        status = row.get("status")
        if status not in {"memenuhi", "tidak_memenuhi", "perlu_klarifikasi"}:
            raise ValueError("semantic_assessments.status tidak dikenal")
        for key in ("finding", "analysis"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"semantic_assessments.{key} wajib berupa teks")
        if status == "perlu_klarifikasi" and (
            not isinstance(row.get("clarification"), str) or not row["clarification"].strip()
        ):
            raise ValueError("semantic_assessments.clarification wajib untuk perlu_klarifikasi")
        ids = row.get("experience_ids", [])
        if not isinstance(ids, list) or any(not isinstance(item, str) or item not in known_ids for item in ids):
            raise ValueError("semantic_assessments.experience_ids menunjuk pengalaman tidak dikenal")
        if len(ids) != len(set(ids)):
            raise ValueError("semantic_assessments.experience_ids duplikat")
        if status == "memenuhi" and not ids:
            raise ValueError("semantic assessment memenuhi wajib menunjuk minimal satu Experience ID")
        refs = row.get("source_refs", [])
        if not isinstance(refs, list) or not refs:
            raise ValueError("semantic_assessments.source_refs wajib berisi bukti kandidat")
        row["code"] = req["audit_code"]
        row["experience_ids"] = ids
        row["kak_refs"] = copy.deepcopy(req.get("source_refs", []))
        row["requirement_text"] = req["text"]
        row["computed"] = False
        result.append(row)
    return result


def _unique_refs(values):
    result, seen = [], set()
    for ref in values:
        key = (ref.get("document_id"), ref.get("page"), ref.get("quote"))
        if key not in seen:
            seen.add(key)
            result.append(copy.deepcopy(ref))
    return result


def _aggregate(code, details):
    label = next(item["label"] for item in AUDIT_CRITERIA if item["code"] == code)
    if not details:
        return {
            "code": code, "applicable": False, "status": None,
            "finding": f"Tidak ada requirement KAK untuk {label}.",
            "analysis": "Pemeriksaan tidak diterapkan karena KAK tidak memuat requirement terstruktur yang sesuai.",
            "source_refs": [], "kak_refs": [], "computed": True,
        }
    statuses = [item["status"] for item in details]
    status = ("tidak_memenuhi" if "tidak_memenuhi" in statuses else
              "perlu_klarifikasi" if "perlu_klarifikasi" in statuses else "memenuhi")
    counts = {name: statuses.count(name) for name in ("memenuhi", "tidak_memenuhi", "perlu_klarifikasi")}
    check = {
        "code": code, "applicable": True, "status": status,
        "finding": (f"{len(details)} requirement diperiksa: {counts['memenuhi']} memenuhi, "
                    f"{counts['tidak_memenuhi']} tidak memenuhi, {counts['perlu_klarifikasi']} perlu klarifikasi."),
        "analysis": f"Hasil agregat {label}; lihat kak_match_details untuk analisis per requirement.",
        "source_refs": _unique_refs([ref for item in details for ref in item.get("source_refs", [])]),
        "kak_refs": _unique_refs([ref for item in details for ref in item.get("kak_refs", [])]),
        "computed": True,
    }
    if status == "perlu_klarifikasi":
        check["clarification"] = "Selesaikan requirement yang masih perlu klarifikasi sebelum menarik kesimpulan KAK final."
    return check


def _detail(requirement, status, finding, analysis, source_refs, *, experience_ids=None, clarification=""):
    item = {
        "requirement_id": requirement["id"],
        "code": requirement["audit_code"],
        "status": status,
        "finding": finding,
        "analysis": analysis,
        "experience_ids": list(experience_ids or []),
        "source_refs": _unique_refs(source_refs),
        "kak_refs": copy.deepcopy(requirement.get("source_refs", [])),
        "requirement_text": requirement["text"],
        "computed": True,
    }
    if status == "perlu_klarifikasi":
        item["clarification"] = clarification or "Periksa kembali bukti kandidat dan requirement KAK."
    return item


def _history_refs(history, *, relevant_only=False):
    refs = []
    for job in history:
        if relevant_only and job.get("relevant") is not True:
            continue
        refs.extend(job.get("source_refs", []))
        refs.extend(job.get("supporting_refs", []))
        for fact in job.get("supporting_facts", []):
            refs.extend(fact.get("source_refs", []))
    return _unique_refs(refs)


def duration_details(requirements, role, history, chronology):
    rows = []
    relevant = chronology.get("relevant_months", 0)
    supported = chronology.get("supported_relevant_months", 0)
    uncertain = chronology.get("uncertain_entries", [])
    refs = _history_refs(history, relevant_only=True)
    for req in requirements:
        if req.get("audit_code") != "experience_duration_match" or not applicable(req, role):
            continue
        minimum = req["minimum_months"]
        if relevant >= minimum and supported >= minimum:
            status = "memenuhi"
            finding = f"Pengalaman relevan {relevant} bulan dan didukung {supported} bulan; minimum KAK {minimum} bulan."
            clarification = ""
        elif relevant < minimum and not uncertain:
            status = "tidak_memenuhi"
            finding = f"Pengalaman relevan {relevant} bulan, di bawah minimum KAK {minimum} bulan."
            clarification = ""
        else:
            status = "perlu_klarifikasi"
            finding = (f"Pengalaman relevan {relevant} bulan, didukung {supported} bulan, minimum KAK {minimum} bulan; "
                       f"{len(uncertain)} entri belum dapat dihitung penuh.")
            clarification = "Lengkapi periode/bukti pengalaman yang belum pasti sebelum menetapkan durasi yang dapat dipakai."
        rows.append(_detail(
            req, status, finding,
            "Durasi memakai union bulan kalender pengalaman yang ditandai relevan; overlap tidak dihitung dua kali.",
            refs, clarification=clarification,
        ))
    return rows


def _level_rank(value):
    return LEVEL_RANK.get(canonical_text(value).replace(" ", ""))


def education_details(requirements, role, education_records):
    rows = []
    for req in requirements:
        if req.get("audit_code") != "education_major_match" or not applicable(req, role):
            continue
        params = req.get("parameters", {})
        minimum_level = params.get("minimum_level", "")
        majors = params.get("accepted_majors", [])
        required_rank = _level_rank(minimum_level) if minimum_level else None
        exact, level_definitely_low, ambiguous = [], True if required_rank is not None else False, False
        for record in education_records:
            rank = _level_rank(record.get("level", ""))
            level_ok = True if required_rank is None else (None if rank is None else rank >= required_rank)
            if level_ok is not False:
                level_definitely_low = False
            major = canonical_text(record.get("major", ""))
            major_ok = True if not majors else any(major == canonical_text(value) for value in majors)
            if level_ok is True and major_ok:
                exact.append(record)
            elif level_ok is None or (level_ok is True and majors and not major_ok):
                ambiguous = True
        refs = _unique_refs([ref for record in education_records
                            for ref in [*record.get("source_refs", []), *record.get("supporting_refs", [])]])
        if exact:
            status = "memenuhi"
            finding = "Ditemukan pendidikan dengan jenjang dan jurusan yang cocok secara terstruktur dengan requirement KAK."
            clarification = ""
        elif not education_records:
            status = "perlu_klarifikasi"
            finding = "Belum ada education_records terstruktur untuk membandingkan pendidikan dengan KAK."
            clarification = "Petakan pendidikan dan bukti ijazah/transkrip yang tersedia."
        elif level_definitely_low:
            status = "tidak_memenuhi"
            finding = f"Seluruh jenjang pendidikan terstruktur berada di bawah minimum {minimum_level}."
            clarification = ""
        else:
            status = "perlu_klarifikasi"
            finding = "Belum ditemukan kecocokan jenjang+jurusan yang exact; kemungkinan ekuivalensi jurusan/gelar perlu review."
            clarification = "Konfirmasi ekuivalensi jurusan/gelar atau lengkapi bukti pendidikan."
        rows.append(_detail(
            req, status, finding,
            "Jenjang dibandingkan dengan urutan pendidikan; jurusan hanya dianggap exact bila normalisasinya sama dengan accepted_majors KAK.",
            refs, clarification=clarification,
        ))
    return rows


def _cert_matches(cert, params):
    scheme = canonical_text(cert.get("scheme", ""))
    level = canonical_text(cert.get("level", ""))
    issuer = canonical_text(cert.get("issuer", ""))
    return (
        (not params.get("schemes") or any(scheme == canonical_text(value) for value in params["schemes"])) and
        (not params.get("levels") or any(level == canonical_text(value) for value in params["levels"])) and
        (not params.get("issuers") or any(issuer == canonical_text(value) for value in params["issuers"]))
    )


def certificate_details(requirements, role, certificates):
    rows = []
    for req in requirements:
        if req.get("audit_code") != "certificate_kak_validity" or not applicable(req, role):
            continue
        params = req.get("parameters", {})
        candidates = [cert for cert in certificates if _cert_matches(cert, params)]
        refs = _unique_refs([ref for cert in (candidates or certificates) for ref in cert.get("source_refs", [])])
        if not certificates:
            status = "tidak_memenuhi"
            finding = "Tidak ada sertifikat yang dipetakan untuk requirement KAK ini."
            clarification = ""
        elif not candidates:
            status = "perlu_klarifikasi"
            finding = "Ada sertifikat, tetapi tidak ada kecocokan exact skema/jenjang/penerbit terhadap parameter KAK."
            clarification = "Konfirmasi ekuivalensi nama skema/jenjang/penerbit atau lampirkan sertifikat yang sesuai."
        else:
            require_current = params.get("require_current", True)
            good, expired, unknown = [], [], []
            for cert in candidates:
                validity = cert.get("validity", "tidak_diketahui")
                if not require_current or validity == "belum_melewati_tanggal_akhir":
                    good.append(cert)
                elif validity in {"kedaluwarsa", "belum_berlaku"}:
                    expired.append(cert)
                else:
                    unknown.append(cert)
            if good:
                status = "memenuhi"
                finding = "Ditemukan sertifikat dengan skema/jenjang/penerbit yang cocok dan kondisi masa berlaku memenuhi parameter KAK."
                clarification = ""
            elif expired and not unknown:
                status = "tidak_memenuhi"
                finding = "Sertifikat yang cocok ditemukan, tetapi tidak berlaku pada tanggal acuan pemeriksaan."
                clarification = ""
            else:
                status = "perlu_klarifikasi"
                finding = "Sertifikat yang cocok ditemukan, tetapi masa berlakunya belum dapat dipastikan."
                clarification = "Konfirmasi tanggal terbit/berlaku sampai atau bukti status sertifikat."
        rows.append(_detail(
            req, status, finding,
            "Kecocokan skema/jenjang/penerbit memakai nilai terstruktur dokumen; status portal identitas dan masa berlaku dokumen tetap dimensi terpisah.",
            refs, clarification=clarification,
        ))
    return rows


def compute_kak_matching(requirements, role, history, chronology, education_records, certificates, semantic_assessments):
    semantic = [copy.deepcopy(row) for row in semantic_assessments]
    details = semantic
    details.extend(duration_details(requirements, role, history, chronology))
    details.extend(education_details(requirements, role, education_records))
    details.extend(certificate_details(requirements, role, certificates))
    order = {item["code"]: item["number"] for item in AUDIT_CRITERIA}
    details.sort(key=lambda item: (order[item["code"]], item["requirement_id"]))
    checks = [_aggregate(code, [item for item in details if item["code"] == code])
              for code in sorted(KAK_MATCH_CODES, key=lambda value: order[value])]
    relevant_ids = {
        exp_id for item in semantic
        if item["code"] == "position_experience_match" and item["status"] == "memenuhi"
        for exp_id in item.get("experience_ids", [])
    }
    return {"details": details, "audit_checks": checks, "relevant_experience_ids": sorted(relevant_ids)}
