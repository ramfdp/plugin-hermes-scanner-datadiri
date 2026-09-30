"""Evidence and completeness rules. No hiring scores or automated hiring decisions."""
import copy
import re
from datetime import date
from .evaluation import (AUDIT_CRITERIA, KAK_MATCH_CODES, SERVER_AUDIT_CODES, assign_experience_ids,
                         evaluate_history_facts, partial_date, validate_audit_checks)
from .kak_matching import (SEMANTIC_MATCH_CODES, applicable, compute_kak_matching,
                           validate_requirement_extension, validate_semantic_assessments)
from .storage import load
from .web import normalized, official_url

CHECK_STATUSES = {"memenuhi", "tidak_memenuhi", "belum_dapat_dinilai"}
PAGE_KINDS = {"cv", "kak", "addendum", "attachment", "unknown"}
REFERENCE_PAGE_KINDS = {"kak", "addendum"}


def require_text(value, label, minimum=1):
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ValueError(f"{label} wajib berupa teks bermakna (minimal {minimum} karakter)")
    return value.strip()


def records(value, label):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label} harus array object")
    return value


def unique(rows, key, label):
    values = [require_text(row.get(key), f"{label}.{key}") for row in rows]
    if len(set(values)) != len(values):
        raise ValueError(f"ID duplikat pada {label}")
    return values


def validate_page_classification(root, manifest, value):
    """Classify every successfully OCR'd page exactly once.

    Older/multi-document clients may omit this field. In that case each page
    inherits its document kind. Single-PDF v0.5 clients should send explicit
    ranges so CV, attachments and KAK pages can coexist inside D001.
    """
    docs = {doc["id"]: doc for doc in manifest["documents"]}
    states = {}
    for doc in manifest["documents"]:
        path = root / "ocr" / f"{doc['id']}.json"
        if path.exists():
            states[doc["id"]] = load(path)

    if value is None:
        derived = []
        for doc in manifest["documents"]:
            state = states.get(doc["id"], {})
            if state.get("success"):
                derived.append({"document_id": doc["id"], "first_page": 1,
                                "last_page": state["page_count"], "kind": doc["kind"]})
        return derived

    rows = copy.deepcopy(records(value, "page_classification"))
    assigned = {doc_id: set() for doc_id, state in states.items() if state.get("success")}
    for row in rows:
        doc_id = row.get("document_id")
        kind = row.get("kind")
        first, last = row.get("first_page"), row.get("last_page")
        if doc_id not in docs:
            raise ValueError("page_classification menunjuk dokumen tidak dikenal")
        state = states.get(doc_id, {})
        if not state.get("success"):
            raise ValueError("page_classification hanya boleh menunjuk OCR yang berhasil")
        if kind not in PAGE_KINDS:
            raise ValueError("page_classification.kind harus cv/kak/addendum/attachment/unknown")
        if type(first) is not int or type(last) is not int or not 1 <= first <= last <= state["page_count"]:
            raise ValueError("Rentang page_classification tidak valid")
        pages = set(range(first, last + 1))
        if assigned[doc_id] & pages:
            raise ValueError("page_classification tumpang tindih pada halaman yang sama")
        assigned[doc_id].update(pages)

    for doc_id, pages in assigned.items():
        state = states[doc_id]
        expected = set(range(1, state["page_count"] + 1))
        if pages != expected:
            raise ValueError(f"Semua halaman {doc_id} wajib memiliki page_classification tepat satu kali")
    return rows


def page_kind(classification, manifest, document_id, page):
    if type(page) is not int:
        return None
    for row in classification or []:
        if row.get("document_id") == document_id and row.get("first_page", 0) <= page <= row.get("last_page", -1):
            return row.get("kind")
    doc = next((item for item in manifest["documents"] if item["id"] == document_id), None)
    return doc.get("kind") if doc else None


def source_refs(root, manifest, refs, *, required=False, kinds=None, page_classification=None):
    refs = records(refs, "source_refs")
    if required and not refs:
        raise ValueError("Bukti dokumen dan halaman wajib")
    docs = {doc["id"]: doc for doc in manifest["documents"]}
    for ref in refs:
        doc = docs.get(ref.get("document_id"))
        page = ref.get("page")
        if not doc:
            raise ValueError("Referensi dokumen tidak sesuai")
        state = load(root / "ocr" / f"{doc['id']}.json")
        if not state.get("success") or type(page) is not int or not 1 <= page <= state["page_count"]:
            raise ValueError("Referensi halaman di luar OCR berhasil")
        if kinds:
            semantic_kind = page_kind(page_classification, manifest, doc["id"], page)
            if semantic_kind not in kinds:
                raise ValueError("Referensi dokumen tidak sesuai")
        quote = require_text(ref.get("quote"), "quote")
        from pathlib import Path
        content = Path(state["markdown_files"][page-1]).read_text(encoding="utf-8")
        if normalized(quote) not in normalized(content):
            raise ValueError(f"Kutipan tidak ditemukan pada {doc['id']} halaman {page}")
    return refs


def validate_plan(root, manifest, payload):
    plan = copy.deepcopy(payload)
    classification = validate_page_classification(root, manifest, plan.get("page_classification"))
    plan["page_classification"] = classification

    roster = records(plan.get("roster"), "roster")
    if not roster:
        raise ValueError("Roster tidak boleh kosong; dokumentasikan CV yang gagal melalui coverage")
    ids = unique(roster, "id", "roster")
    expected = manifest.get('expected_person_count')
    if expected is not None and len(roster) != expected:
        raise ValueError('Jumlah roster berbeda dari expected_person_count pengguna')
    for person in roster:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", person["id"]):
            raise ValueError("ID personel hanya huruf, angka, _, -")
        require_text(person.get("name"), "roster.name")
        require_text(person.get("role"), "roster.role")
        source_refs(root, manifest, person.get("cv_refs", []), required=True, kinds={"cv"},
                    page_classification=classification)
        inventory = records(person.get("certificate_inventory", []), "certificate_inventory")
        unique(inventory, "id", "certificate_inventory")
        for cert in inventory:
            source_refs(root, manifest, cert.get("source_refs", []), required=True,
                        kinds={"cv", "attachment"}, page_classification=classification)

    requirements = records(plan.get("requirements"), "requirements")
    unique(requirements, "id", "requirements")
    for requirement in requirements:
        require_text(requirement.get("role"), "requirement.role (atau *)")
        require_text(requirement.get("text"), "requirement.text")
        if requirement.get("kind") not in {"education", "experience", "certificate", "other"}:
            raise ValueError("Jenis requirement tidak dikenal")
        minimum = requirement.get("minimum_months")
        if minimum is not None and (type(minimum) is not int or minimum < 0):
            raise ValueError("minimum_months harus integer >= 0 atau null")
        req_refs = source_refs(root, manifest, requirement.get("source_refs", []), required=True,
                               kinds=REFERENCE_PAGE_KINDS, page_classification=classification)
        validate_requirement_extension(requirement, " ".join(ref["quote"] for ref in req_refs))

    kak = plan.get("kak")
    if not isinstance(kak, dict):
        raise ValueError("kak wajib object metadata: title, version, package_id, analysis")
    require_text(kak.get("analysis"), "kak.analysis", 20)
    has_kak_pages = any(row["kind"] == "kak" for row in classification)
    kak["status"] = "dokumen_diberikan_belum_diautentikasi" if has_kak_pages else "tidak_tersedia"
    # A matching public package can support provenance, never blanket legal validity.
    for rid in kak.get("receipt_ids", []):
        receipt = read_receipt(root, rid)
        identity = [kak.get("package_id", ""), kak.get("version", "")]
        if (receipt['success'] and receipt['evidence_kind'] == 'page' and receipt['urls'] and
                all(official_url(u) for u in receipt['urls']) and all(identity) and
                all(normalized(x) in normalized(receipt['content']) for x in identity)):
            kak["status"] = "identitas_paket_dan_versi_ditemukan_pada_sumber"

    coverage = records(plan.get("coverage"), "coverage")
    if any(item.get('document_id') not in {d['id'] for d in manifest['documents']} for item in coverage):
        raise ValueError('Coverage menunjuk dokumen tidak dikenal')
    for doc in manifest["documents"]:
        state = load(root / "ocr" / f"{doc['id']}.json")
        if not state.get("success"):
            continue
        if doc["kind"] not in {"cv", "attachment"}:
            continue
        covered = set()
        for item in [x for x in coverage if x.get("document_id") == doc["id"]]:
            first, last = item.get("first_page"), item.get("last_page")
            if type(first) is not int or type(last) is not int or not 1 <= first <= last <= state["page_count"]:
                raise ValueError("Rentang coverage tidak valid")
            targets = item.get("person_ids", [])
            if not isinstance(targets, list) or any(pid not in ids for pid in targets):
                raise ValueError("Coverage menunjuk personel yang tidak terdaftar")
            semantic_kinds = {page_kind(classification, manifest, doc["id"], page) for page in range(first, last + 1)}
            reason = item.get("reason")
            if targets and semantic_kinds & REFERENCE_PAGE_KINDS:
                raise ValueError("Halaman KAK/addendum tidak boleh dimiliki personel pada coverage")
            if not targets:
                if reason not in {"blank", "cover", "unassigned", "unreadable", "reference"}:
                    raise ValueError("Halaman tanpa personel memerlukan reason blank/cover/unassigned/unreadable/reference")
                if reason == "reference" and not semantic_kinds <= REFERENCE_PAGE_KINDS:
                    raise ValueError("reason reference hanya untuk halaman KAK/addendum")
                if semantic_kinds <= REFERENCE_PAGE_KINDS and reason != "reference":
                    raise ValueError("Halaman KAK/addendum tanpa personel harus memakai reason reference")
            covered.update(range(first, last+1))
        if covered != set(range(1, state["page_count"]+1)):
            raise ValueError(f"Semua halaman {doc['id']} harus memiliki coverage")
    for person in roster:
        for ref in person['cv_refs']:
            if not any(x.get('document_id') == ref['document_id'] and person['id'] in x.get('person_ids', []) and
                       x['first_page'] <= ref['page'] <= x['last_page'] for x in coverage):
                raise ValueError("cv_refs personel harus sesuai coverage")
    return plan

def read_receipt(root, receipt_id):
    if not isinstance(receipt_id, str) or not re.fullmatch(r"W[a-f0-9]{16}", receipt_id):
        raise ValueError("receipt_id tidak valid")
    return load(root / "web" / f"{receipt_id}.json")


def chronology(history, as_of=None):
    """Union of calendar months when month precision is actually available."""
    all_months, relevant, supported, uncertain = set(), set(), set(), []
    for number, job in enumerate(history, 1):
        start, end = partial_date(job.get("start_date")), partial_date(job.get("end_date"))
        if not start["valid"] or not end["valid"]:
            uncertain.append(number)
            continue
        if start["first"] > end["last"]:
            raise ValueError("Tanggal akhir pengalaman mendahului tanggal mulai")
        # Year-only dates do not reveal which months were actually worked.
        if start["precision"] == "year" or end["precision"] == "year":
            uncertain.append(number)
            continue
        a = start["first"].year * 12 + start["first"].month - 1
        b = end["last"].year * 12 + end["last"].month - 1
        if as_of is not None:
            # Preserve the historical policy: the unfinished assessment month
            # and future months are not counted as experience already earned.
            cutoff = as_of.year * 12 + as_of.month - 2
            if b > cutoff:
                uncertain.append(number)
            b = min(b, cutoff)
        if b < a:
            continue
        months = set(range(a, b + 1))
        all_months |= months
        if job.get("relevant") is True:
            relevant |= months
            if job.get("supporting_refs") or job.get("supporting_facts"):
                supported |= months
    return {
        "calendar_months_unique": len(all_months),
        "relevant_months": len(relevant),
        "supported_relevant_months": len(supported),
        "uncertain_entries": list(dict.fromkeys(uncertain)),
        "method": "Bulan kalender inklusif; overlap dihitung sekali. YYYY-MM dan YYYY-MM-DD dapat dihitung pada tingkat bulan; YYYY tetap tidak diubah menjadi bulan tebakan. Bulan penilaian yang belum selesai dan bulan berikutnya dikecualikan.",
    }

def certificate_result(root, manifest, certificate, holder, as_of):
    cert = copy.deepcopy(certificate)
    require_text(cert.get("analysis"), "certificate.analysis", 30)
    source_refs(root, manifest, cert.get("source_refs", []), required=True)
    document_text = normalized(" ".join(ref['quote'] for ref in cert['source_refs']))
    for key in ('number', 'holder', 'scheme', 'issuer'):
        value = cert.get(key)
        if value and normalized(value) not in document_text:
            raise ValueError(f"certificate.{key} tidak didukung kutipan dokumen")
    status, reason = "belum_dapat_diverifikasi", "Belum ada hasil portal resmi yang memadai."
    cert["checked_at"] = None
    if cert.get("receipt_id"):
        receipt = read_receipt(root, cert["receipt_id"])
        cert["checked_at"] = receipt['checked_at']
        quote = require_text(cert.get("quote"), "certificate.quote")
        if len(quote) > 2000 or normalized(quote) not in normalized(receipt['content']):
            raise ValueError("Kutipan sertifikat tidak ditemukan pada receipt web")
        if receipt['success'] and receipt['evidence_kind'] == 'page' and receipt['urls'] and all(official_url(u) for u in receipt['urls']):
            values = [cert.get(k, '') for k in ('number', 'holder', 'scheme', 'issuer')]
            matches = [isinstance(v, str) and bool(v.strip()) and bool(re.search(r'(?<!\w)' + re.escape(normalized(v)) + r'(?!\w)', normalized(quote))) for v in values]
            cert['matched_fields'] = dict(zip(('number', 'holder', 'scheme', 'issuer'), matches))
            if all(matches) and normalized(cert.get('holder', '')) == normalized(holder):
                status, reason = "terverifikasi", "Nomor, pemegang, skema dan penerbit ditemukan pada receipt portal resmi; tetap perlu review manual."
            elif matches[0]:
                status, reason = "sebagian_terverifikasi", "Nomor ditemukan, tetapi kecocokan identitas/skema/penerbit belum lengkap."
    # Identity verification and date validity are independent dimensions.
    validity = "tidak_diketahui"
    expiry, issued = cert.get('expires_on'), cert.get('issued_on')
    if issued and expiry and date.fromisoformat(issued) > date.fromisoformat(expiry):
        raise ValueError("Tanggal terbit sertifikat melewati tanggal kedaluwarsa")
    if expiry:
        validity = "kedaluwarsa" if date.fromisoformat(expiry) < as_of else "belum_melewati_tanggal_akhir"
    if issued and date.fromisoformat(issued) > as_of:
        validity = "belum_berlaku"
    cert.update(status=status, reason=reason, validity=validity, validity_basis="Tanggal pada dokumen yang dipetakan, bukan jaminan tidak dicabut")
    return cert


def validate_person(root, manifest, plan, payload):
    person = copy.deepcopy(payload)
    roster = next((p for p in plan['roster'] if p['id'] == person.get('id')), None)
    if roster is None:
        raise ValueError("Personel tidak ada dalam roster")
    person['name'], person['role'] = roster['name'], roster['role']
    require_text(person.get('summary'), 'summary', 30)
    classification = plan.get('page_classification', [])

    def own_refs(refs):
        for ref in refs:
            semantic_kind = page_kind(classification, manifest, ref.get('document_id'), ref.get('page'))
            if semantic_kind in {'cv', 'attachment'} and not any(
                item['document_id'] == ref['document_id'] and person['id'] in item.get('person_ids', []) and
                item['first_page'] <= ref['page'] <= item['last_page'] for item in plan['coverage']
            ):
                raise ValueError('Bukti halaman bukan milik personel menurut coverage')

    for group in ('checks', 'employment_history', 'certificates'):
        for row in records(person.get(group, []), group):
            own_refs(row.get('source_refs', []))
            own_refs(row.get('supporting_refs', []))
    identity = person.get('identity')
    if not isinstance(identity, dict):
        raise ValueError("identity wajib object (education, certificate_summary, claimed_months, nik)")
    if not isinstance(identity.get('nik', ''), str):
        raise ValueError("NIK harus string; jangan konversi menjadi angka")
    if identity.get('nik'):
        identity['nik'] = '[ID_REDACTED]'
    claimed = identity.get('claimed_months')
    if claimed is not None and (type(claimed) is not int or claimed < 0):
        raise ValueError("claimed_months harus integer >= 0 atau null")
    applicable_requirements = {r['id']: r for r in plan['requirements']
                               if r['role'] == '*' or normalized(r['role']) == normalized(roster['role'])}
    legacy_required = {rid: requirement for rid, requirement in applicable_requirements.items()
                       if not requirement.get('audit_code')}
    checks = records(person.get('checks'), 'checks')
    if set(unique(checks, 'requirement_id', 'checks')) != set(legacy_required):
        raise ValueError("checks legacy harus mencakup tepat requirement tanpa audit_code untuk role personel")
    for check in checks:
        if check.get('status') not in CHECK_STATUSES:
            raise ValueError("Status check harus memenuhi/tidak_memenuhi/belum_dapat_dinilai")
        require_text(check.get('finding'), 'finding')
        require_text(check.get('analysis'), 'analysis', 30)
        source_refs(root, manifest, check.get('source_refs', []), required=check['status'] != 'belum_dapat_dinilai')
        if check['status'] == 'belum_dapat_dinilai':
            require_text(check.get('clarification'), 'clarification')
        check['requirement'] = legacy_required[check['requirement_id']]['text']

    history = assign_experience_ids(records(person.get('employment_history', []), 'employment_history'))
    organization_fields = ('client', 'consultant', 'contractor', 'represented_organization')
    for job in history:
        require_text(job.get('employer'), 'employer')
        for field in organization_fields:
            value = job.get(field, '')
            if value is not None and not isinstance(value, str):
                raise ValueError(f'employment_history.{field} harus string atau null')
            if value is None:
                job[field] = ''
        source_refs(root, manifest, job.get('source_refs', []), required=True, kinds={'cv'},
                    page_classification=classification)
        source_refs(root, manifest, job.get('supporting_refs', []), kinds={'cv', 'attachment'},
                    page_classification=classification)
        supporting_facts = records(job.get('supporting_facts', []), 'supporting_facts')
        for fact in supporting_facts:
            if not any(isinstance(fact.get(field), str) and fact.get(field).strip()
                       for field in ('project', 'employer', 'role', 'start_date', 'end_date',
                                     *organization_fields)):
                raise ValueError('supporting_facts harus memuat minimal satu fakta proyek/organisasi/jabatan/periode')
            for field in ('project', 'employer', 'role', 'start_date', 'end_date', *organization_fields):
                value = fact.get(field)
                if value is not None and not isinstance(value, str):
                    raise ValueError(f'supporting_facts.{field} harus string atau null')
            refs = source_refs(root, manifest, fact.get('source_refs', []), required=True,
                               kinds={'cv', 'attachment'}, page_classification=classification)
            own_refs(refs)
            strict_evidence = fact.get('strict_evidence', False)
            if not isinstance(strict_evidence, bool):
                raise ValueError('supporting_facts.strict_evidence harus boolean')
            fact['strict_evidence'] = strict_evidence
            if strict_evidence:
                evidence_text = normalized(" ".join(ref['quote'] for ref in refs))
                for field in ('project', 'employer', 'role', 'client', 'consultant', 'contractor',
                              'represented_organization', 'start_date', 'end_date'):
                    value = fact.get(field)
                    if isinstance(value, str) and value.strip() and normalized(value) not in evidence_text:
                        raise ValueError(f'supporting_facts.{field} tidak didukung kutipan dokumen')
        job['supporting_facts'] = supporting_facts
    person['employment_history'] = history

    education_records = records(person.get('education_records', []), 'education_records')
    for record in education_records:
        for field in ('level', 'major', 'institution', 'degree'):
            value = record.get(field, '')
            if value is not None and not isinstance(value, str):
                raise ValueError(f'education_records.{field} harus string atau null')
            if value is None:
                record[field] = ''
        refs = source_refs(root, manifest, record.get('source_refs', []), required=True,
                           kinds={'cv', 'attachment'}, page_classification=classification)
        own_refs(refs)
        support = source_refs(root, manifest, record.get('supporting_refs', []),
                              kinds={'cv', 'attachment'}, page_classification=classification)
        own_refs(support)
        evidence_text = normalized(" ".join(ref['quote'] for ref in [*refs, *support]))
        for field in ('level', 'major', 'institution', 'degree'):
            value = record.get(field)
            if isinstance(value, str) and value.strip() and normalized(value) not in evidence_text:
                raise ValueError(f'education_records.{field} tidak didukung kutipan dokumen')
    person['education_records'] = education_records

    semantic_assessments = validate_semantic_assessments(
        person.get('semantic_assessments', []), plan['requirements'], person['role'],
        [job['id'] for job in history])
    for assessment in semantic_assessments:
        refs = source_refs(root, manifest, assessment.get('source_refs', []), required=True,
                           kinds={'cv', 'attachment'}, page_classification=classification)
        own_refs(refs)
        source_refs(root, manifest, assessment.get('kak_refs', []), required=True,
                    kinds=REFERENCE_PAGE_KINDS, page_classification=classification)
    person['semantic_assessments'] = semantic_assessments

    position_requirements = [req for req in plan['requirements']
                             if req.get('audit_code') == 'position_experience_match'
                             and applicable(req, person['role'])]
    if position_requirements:
        relevant_ids = {exp_id for assessment in semantic_assessments
                        if assessment['code'] == 'position_experience_match'
                        and assessment['status'] == 'memenuhi'
                        for exp_id in assessment.get('experience_ids', [])}
        for job in history:
            job['relevant'] = job['id'] in relevant_ids

    assessment_date = date.fromisoformat(manifest['assessment_date'])
    person['chronology'] = chronology(history, assessment_date)

    certificates = records(person.get('certificates'), 'certificates')
    inventory = {cert['id']: cert for cert in roster.get('certificate_inventory', [])}
    if set(unique(certificates, 'inventory_id', 'certificates')) != set(inventory):
        raise ValueError('certificates harus mencakup semua certificate_inventory, tanpa tambahan atau duplikat')
    for cert in certificates:
        if cert.get('source_refs') != inventory[cert['inventory_id']]['source_refs']:
            raise ValueError('Bukti sertifikat harus sama dengan inventory plan')
    if not certificates:
        require_text(person.get('certificate_limitation'), 'certificate_limitation')
    person['certificates'] = [certificate_result(root, manifest, cert, person['name'], assessment_date) for cert in certificates]

    kak_matching = compute_kak_matching(
        plan['requirements'], person['role'], history, person['chronology'],
        education_records, person['certificates'], semantic_assessments)
    person['kak_match_details'] = kak_matching['details']

    submitted_audit_checks = validate_audit_checks(person.get('audit_checks', []))
    user_audit_checks = []
    for check in submitted_audit_checks:
        if check.get('code') in SERVER_AUDIT_CODES:
            if check.get('computed') is True:
                continue  # Re-validation of a stored server result; recompute it below.
            raise ValueError('Audit #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12 dikelola server dan tidak boleh ditimpa payload')
        user_audit_checks.append(check)
    facts = evaluate_history_facts(history, assessment_date)
    person['fact_analysis'] = {key: value for key, value in facts.items() if key != 'audit_checks'}
    audit_checks = [*user_audit_checks, *facts['audit_checks'], *kak_matching['audit_checks']]
    order = {item['code']: item['number'] for item in AUDIT_CRITERIA}
    audit_checks.sort(key=lambda check: order[check['code']])
    for check in audit_checks:
        require_evidence = check.get('applicable', True) and check.get('status') in {'memenuhi', 'tidak_memenuhi'}
        source_refs(root, manifest, check.get('source_refs', []), required=require_evidence)
        own_refs(check.get('source_refs', []))
        source_refs(root, manifest, check.get('kak_refs', []), kinds=REFERENCE_PAGE_KINDS,
                    page_classification=classification)
    person['audit_checks'] = audit_checks

    findings = person.get('findings', [])
    if not isinstance(findings, list) or any(not isinstance(x, str) for x in findings):
        raise ValueError("findings harus array teks")
    employers = records(person.get('employer_checks', []), 'employer_checks')
    if {normalized(job['employer']) for job in history} != {normalized(item.get('employer', '')) for item in employers}:
        raise ValueError("employer_checks harus mencakup semua perusahaan dalam riwayat")
    for employer in employers:
        require_text(employer.get('analysis'), 'employer.analysis', 20)
        employer['status'] = 'belum_dapat_diverifikasi'
        if employer.get('receipt_id'):
            receipt = read_receipt(root, employer['receipt_id'])
            quote = require_text(employer.get('quote'), 'employer.quote')
            if normalized(quote) not in normalized(receipt['content']):
                raise ValueError("Kutipan perusahaan tidak ditemukan pada receipt")
            if receipt['success'] and receipt['evidence_kind'] == 'page' and normalized(employer['employer']) in normalized(receipt['content']):
                employer['status'] = 'nama_ditemukan_pada_sumber_bukan_bukti_hubungan_kerja'
    structured_applicable = [check for check in person['audit_checks']
                             if check.get('code') in KAK_MATCH_CODES and check.get('applicable')]
    person['overall'] = (
        'ada_kriteria_tidak_memenuhi' if any(check.get('status') == 'tidak_memenuhi' for check in structured_applicable) else
        'perlu_klarifikasi' if any(check.get('status') == 'perlu_klarifikasi' for check in structured_applicable) else
        'kriteria_diperiksa_memenuhi' if structured_applicable else
        'tidak_ada_kriteria_KAK' if not checks else
        'ada_kriteria_tidak_memenuhi' if any(check['status'] == 'tidak_memenuhi' for check in checks) else
        'perlu_klarifikasi' if any(check['status'] == 'belum_dapat_dinilai' for check in checks) else
        'kriteria_diperiksa_memenuhi')
    person['review_note'] = 'Hasil bantu pemeriksaan dokumen; bukan keputusan menerima/menolak personel.'
    return person

