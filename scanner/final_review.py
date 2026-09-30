"""Final review engine for Scanner Data Diri 0.7.0.

Implements:
- #13 CV vs supporting-document cross-check
- #14 structured anomaly aggregation
- #15 deterministic final KAK conclusion

Document conflicts are review facts, not accusations of falsification. They become
perlu_klarifikasi unless a separate KAK requirement itself is not met.
"""
import copy
from .evaluation import AUDIT_CRITERIA, FINAL_AUDIT_CODES, KAK_MATCH_CODES, canonical_text, date_values_compatible
FINAL_LABELS = {
    "memenuhi": "Memenuhi",
    "tidak_memenuhi": "Tidak Memenuhi",
    "perlu_klarifikasi": "Perlu Klarifikasi",
}
CROSS_FIELDS = (
    "project", "employer", "role", "client", "consultant",
    "contractor", "represented_organization", "start_date", "end_date",
)


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


def _refs_from_history(history):
    refs = []
    for job in history:
        refs.extend(job.get("source_refs", []))
        refs.extend(job.get("supporting_refs", []))
        for fact in job.get("supporting_facts", []):
            refs.extend(fact.get("source_refs", []))
    return _unique_refs(refs)


def _refs_from_education(records):
    refs = []
    for record in records:
        refs.extend(record.get("source_refs", []))
        refs.extend(record.get("supporting_refs", []))
    return _unique_refs(refs)


def _refs_from_certificates(certificates):
    return _unique_refs([ref for cert in certificates for ref in cert.get("source_refs", [])])


def _quote_text(refs):
    return canonical_text(" ".join(ref.get("quote", "") for ref in refs))


def _same(field, left, right):
    if field in {"start_date", "end_date"}:
        return date_values_compatible(left, right)
    return bool(canonical_text(left)) and canonical_text(left) == canonical_text(right)


def evaluate_cv_supporting_documents(identity, history, education_records, certificates):
    details, conflicts, missing = [], [], []
    all_refs = []
    comparable_count = 0

    # Employment/project claims versus structured facts extracted from attachments.
    for job in history:
        job_id = job.get("id")
        facts = job.get("supporting_facts", [])
        row = {"type": "experience", "experience_id": job_id, "fields": []}
        all_refs.extend(job.get("source_refs", []))
        all_refs.extend(job.get("supporting_refs", []))
        for fact in facts:
            all_refs.extend(fact.get("source_refs", []))
        for field in CROSS_FIELDS:
            claimed = job.get(field)
            if not isinstance(claimed, str) or not claimed.strip():
                continue
            comparable_count += 1
            supported_values = [
                fact.get(field) for fact in facts
                if isinstance(fact.get(field), str) and fact.get(field).strip()
            ]
            if not supported_values:
                item = {
                    "experience_id": job_id, "field": field, "cv_value": claimed,
                    "status": "missing_support",
                }
                missing.append(item)
                row["fields"].append(item)
                continue
            matches = [value for value in supported_values if _same(field, claimed, value)]
            if matches:
                row["fields"].append({
                    "experience_id": job_id, "field": field, "cv_value": claimed,
                    "support_value": matches[0], "status": "match",
                })
            else:
                item = {
                    "experience_id": job_id, "field": field, "cv_value": claimed,
                    "support_values": supported_values, "status": "conflict",
                }
                conflicts.append(item)
                row["fields"].append(item)
        details.append(row)

    # Education claim in CV versus diploma/transcript references.
    identity_education = canonical_text(identity.get("education", ""))
    for index, record in enumerate(education_records, 1):
        source_refs = record.get("source_refs", [])
        supporting_refs = record.get("supporting_refs", [])
        all_refs.extend(source_refs)
        all_refs.extend(supporting_refs)
        row = {"type": "education", "record": index, "fields": []}
        source_text, support_text = _quote_text(source_refs), _quote_text(supporting_refs)
        core = [("level", record.get("level", "")), ("major", record.get("major", ""))]
        for field, value in core:
            if not isinstance(value, str) or not value.strip():
                continue
            comparable_count += 1
            canonical = canonical_text(value)
            cv_match = canonical in source_text or canonical in identity_education
            support_match = canonical in support_text if supporting_refs else False
            if not supporting_refs:
                item = {
                    "record": index, "field": field, "cv_value": value,
                    "status": "missing_support",
                }
                missing.append(item)
            elif cv_match and support_match:
                item = {
                    "record": index, "field": field, "cv_value": value,
                    "support_value": value, "status": "match",
                }
            elif cv_match and not support_match:
                item = {
                    "record": index, "field": field, "cv_value": value,
                    "status": "support_does_not_show_value",
                }
                missing.append(item)
            else:
                item = {
                    "record": index, "field": field, "cv_value": value,
                    "status": "cv_does_not_show_value",
                }
                conflicts.append(item)
            row["fields"].append(item)
        details.append(row)

    # Certificate summary in CV versus mapped certificate attachments.
    summary = canonical_text(identity.get("certificate_summary", ""))
    all_refs.extend(_refs_from_certificates(certificates))
    if summary:
        comparable_count += 1
        if not certificates:
            item = {"field": "certificate_summary", "cv_value": identity.get("certificate_summary"),
                    "status": "missing_support"}
            missing.append(item)
            details.append({"type": "certificate", "fields": [item]})
        else:
            matches = []
            for cert in certificates:
                scheme = canonical_text(cert.get("scheme", ""))
                level = canonical_text(cert.get("level", ""))
                scheme_ok = bool(scheme) and scheme in summary
                level_ok = not level or level in summary
                if scheme_ok and level_ok:
                    matches.append(cert)
            if matches:
                details.append({"type": "certificate", "fields": [{
                    "field": "certificate_summary", "cv_value": identity.get("certificate_summary"),
                    "support_value": matches[0].get("scheme", ""), "status": "match",
                }]})
            else:
                item = {
                    "field": "certificate_summary", "cv_value": identity.get("certificate_summary"),
                    "support_values": [cert.get("scheme", "") for cert in certificates],
                    "status": "conflict",
                }
                conflicts.append(item)
                details.append({"type": "certificate", "fields": [item]})

    refs = _unique_refs(all_refs)
    if comparable_count == 0:
        return {
            "details": details, "conflicts": conflicts, "missing": missing,
            "check": {
                "code": "cv_supporting_document_match",
                "applicable": False,
                "status": None,
                "finding": "Tidak ada klaim terstruktur yang dapat dicross-check terhadap dokumen pendukung.",
                "analysis": "Pemeriksaan tidak diterapkan karena tidak ada field CV/riwayat/pendidikan/sertifikat yang dapat dibandingkan.",
                "source_refs": [], "kak_refs": [], "computed": True,
            },
        }
    if conflicts or missing:
        status = "perlu_klarifikasi"
        finding = (f"Cross-check CV vs dokumen pendukung menemukan {len(conflicts)} konflik "
                   f"dan {len(missing)} field/bukti yang belum lengkap.")
        clarification = "Konfirmasi nilai yang berbeda dan lengkapi dokumen pendukung yang belum memuat fakta terkait."
    else:
        status = "memenuhi"
        finding = "Data terstruktur yang dapat dicross-check konsisten antara CV dan dokumen pendukung."
        clarification = ""

    check = {
        "code": "cv_supporting_document_match",
        "applicable": True,
        "status": status,
        "finding": finding,
        "analysis": "Cross-check membandingkan field terstruktur tanpa menganggap dokumen yang berbeda sebagai bukti pemalsuan.",
        "source_refs": refs,
        "kak_refs": [],
        "computed": True,
    }
    if clarification:
        check["clarification"] = clarification
    return {"details": details, "conflicts": conflicts, "missing": missing, "check": check}


def evaluate_anomalies(person, fact_analysis, cross_check):
    anomalies, refs = [], []

    def add(code, detail, *, experience_ids=None, field=None, source_refs=None, material=True):
        anomalies.append({
            "id": f"A{len(anomalies)+1:03d}",
            "code": code,
            "detail": detail,
            "experience_ids": list(experience_ids or []),
            "field": field,
            "material": bool(material),
            "source_refs": _unique_refs(source_refs or []),
        })
        refs.extend(source_refs or [])

    period = fact_analysis.get("period", {})
    for item in period.get("issues", []):
        exp = item.get("experience_id")
        add(
            "period_" + item.get("type", "issue"),
            item.get("detail") or f"Isu periode pada {exp}.",
            experience_ids=[exp] if exp else [],
            field=item.get("field"),
            source_refs=_refs_from_history([job for job in person.get("employment_history", []) if job.get("id") == exp]),
        )

    consistency = fact_analysis.get("consistency", {})
    for item in consistency.get("conflicts", []):
        exp = item.get("experience_id")
        add(
            "consistency_conflict",
            f"{exp} field {item.get('field')} berbeda antara CV dan fakta pendukung.",
            experience_ids=[exp] if exp else [],
            field=item.get("field"),
            source_refs=_refs_from_history([job for job in person.get("employment_history", []) if job.get("id") == exp]),
        )

    for pair in fact_analysis.get("overlaps", {}).get("pairs", []):
        ids = [pair["left_id"], pair["right_id"]]
        add(
            "experience_overlap",
            f"{pair['left_id']} dan {pair['right_id']} overlap {pair['overlap_start']} s.d. {pair['overlap_end']}.",
            experience_ids=ids,
            source_refs=_refs_from_history([job for job in person.get("employment_history", []) if job.get("id") in ids]),
            material=False,
        )

    for pair in fact_analysis.get("duplicates", {}).get("pairs", []):
        ids = [pair["left_id"], pair["right_id"]]
        add(
            "experience_duplicate_" + pair.get("type", "possible"),
            f"{pair['left_id']} dan {pair['right_id']} terdeteksi sebagai {pair.get('type', 'possible')} duplicate.",
            experience_ids=ids,
            source_refs=_refs_from_history([job for job in person.get("employment_history", []) if job.get("id") in ids]),
        )

    for item in cross_check.get("conflicts", []):
        add(
            "cv_support_conflict",
            f"Cross-check dokumen berbeda pada field {item.get('field')}.",
            experience_ids=[item["experience_id"]] if item.get("experience_id") else [],
            field=item.get("field"),
            source_refs=cross_check.get("check", {}).get("source_refs", []),
        )
    for item in cross_check.get("missing", []):
        add(
            "cv_support_missing",
            f"Dokumen pendukung belum cukup untuk field {item.get('field')}.",
            experience_ids=[item["experience_id"]] if item.get("experience_id") else [],
            field=item.get("field"),
            source_refs=cross_check.get("check", {}).get("source_refs", []),
            material=False,
        )

    claimed = person.get("identity", {}).get("claimed_months")
    unique_months = person.get("chronology", {}).get("calendar_months_unique")
    uncertain = person.get("chronology", {}).get("uncertain_entries", [])
    if isinstance(claimed, int) and isinstance(unique_months, int) and not uncertain and abs(claimed - unique_months) > 1:
        add(
            "claimed_duration_mismatch",
            f"Klaim pengalaman {claimed} bulan berbeda dari kronologi unik {unique_months} bulan.",
            source_refs=_refs_from_history(person.get("employment_history", [])),
        )

    anomalies = list({(a["code"], tuple(a["experience_ids"]), a.get("field"), a["detail"]): a for a in anomalies}.values())
    for index, item in enumerate(anomalies, 1):
        item["id"] = f"A{index:03d}"

    all_refs = _unique_refs(refs)
    fallback_refs = _unique_refs([
        *_refs_from_history(person.get("employment_history", [])),
        *_refs_from_education(person.get("education_records", [])),
        *_refs_from_certificates(person.get("certificates", [])),
    ])
    if not anomalies and not fallback_refs:
        return {
            "items": [],
            "check": {
                "code": "data_anomaly", "applicable": False, "status": None,
                "finding": "Tidak ada data terstruktur yang cukup untuk menjalankan anomaly engine.",
                "analysis": "Pemeriksaan anomali tidak diterapkan pada personel tanpa data terstruktur.",
                "source_refs": [], "kak_refs": [], "computed": True,
            },
        }
    if anomalies:
        material = sum(1 for item in anomalies if item["material"])
        finding = f"Ditemukan {len(anomalies)} anomali/isu data; {material} dikategorikan material untuk klarifikasi."
        status = "perlu_klarifikasi"
        clarification = "Tinjau daftar anomali dan perbaiki/konfirmasi data sebelum kesimpulan final dianggap tuntas."
    else:
        finding = "Tidak ditemukan anomali terstruktur dari pemeriksaan yang tersedia."
        status = "memenuhi"
        clarification = ""

    check = {
        "code": "data_anomaly",
        "applicable": True,
        "status": status,
        "finding": finding,
        "analysis": "Anomali dikompilasi dari periode, konsistensi, overlap, duplikasi, cross-check dokumen, dan perbedaan klaim durasi.",
        "source_refs": all_refs or fallback_refs,
        "kak_refs": [],
        "computed": True,
    }
    if clarification:
        check["clarification"] = clarification
    return {"items": anomalies, "check": check}


def final_conclusion(audit_checks, legacy_checks, requirements, kak):
    considered = [
        check for check in audit_checks
        if check.get("code") != "kak_conclusion" and check.get("applicable")
    ]
    legacy_statuses = [check.get("status") for check in legacy_checks]
    has_kak_criteria = bool(requirements or legacy_checks)

    if any(check.get("status") == "tidak_memenuhi" for check in considered) or "tidak_memenuhi" in legacy_statuses:
        status = "tidak_memenuhi"
        finding = "Setidaknya satu kriteria KAK yang berlaku berstatus Tidak Memenuhi."
    elif (not has_kak_criteria or kak.get("status") == "tidak_tersedia" or
          any(check.get("status") == "perlu_klarifikasi" for check in considered) or
          "belum_dapat_dinilai" in legacy_statuses):
        status = "perlu_klarifikasi"
        if not has_kak_criteria or kak.get("status") == "tidak_tersedia":
            finding = "KAK/persyaratan yang dapat dipakai belum cukup untuk menyimpulkan pemenuhan."
        else:
            finding = "Tidak ada kriteria yang pasti Tidak Memenuhi, tetapi masih ada audit atau bukti yang memerlukan klarifikasi."
    else:
        status = "memenuhi"
        finding = "Seluruh kriteria KAK yang berlaku dan seluruh audit yang relevan berstatus Memenuhi."

    source_refs = _unique_refs(
        [ref for check in considered for ref in check.get("source_refs", [])] +
        [ref for check in legacy_checks for ref in check.get("source_refs", [])]
    )
    kak_refs = _unique_refs([
        ref for check in considered for ref in check.get("kak_refs", [])
    ] + [
        ref for requirement in requirements for ref in requirement.get("source_refs", [])
    ])
    check = {
        "code": "kak_conclusion",
        "applicable": True,
        "status": status,
        "finding": finding,
        "analysis": "Kesimpulan final dihitung deterministik: Tidak Memenuhi mengalahkan Klarifikasi; Klarifikasi mengalahkan Memenuhi. Tidak ada KAK tidak pernah dianggap Memenuhi.",
        "source_refs": source_refs,
        "kak_refs": kak_refs,
        "computed": True,
    }
    if status == "perlu_klarifikasi":
        check["clarification"] = "Selesaikan seluruh audit/bukti yang masih terbuka sebelum menetapkan pemenuhan final."
    return {
        "status": status,
        "label": FINAL_LABELS[status],
        "finding": finding,
        "check": check,
    }


def finalize_person_review(person, requirements, kak, audit_checks, legacy_checks):
    cross_check = evaluate_cv_supporting_documents(
        person.get("identity", {}),
        person.get("employment_history", []),
        person.get("education_records", []),
        person.get("certificates", []),
    )
    person["document_cross_check"] = {
        key: value for key, value in cross_check.items() if key != "check"
    }
    audit_checks = [*audit_checks, cross_check["check"]]

    anomaly = evaluate_anomalies(person, person.get("fact_analysis", {}), cross_check)
    person["anomalies"] = anomaly["items"]
    audit_checks.append(anomaly["check"])

    conclusion = final_conclusion(audit_checks, legacy_checks, requirements, kak)
    audit_checks.append(conclusion["check"])
    person["final_conclusion"] = {
        "status": conclusion["status"],
        "label": conclusion["label"],
        "finding": conclusion["finding"],
    }

    order = {item["code"]: item["number"] for item in AUDIT_CRITERIA}
    audit_checks.sort(key=lambda check: order[check["code"]])
    return audit_checks
