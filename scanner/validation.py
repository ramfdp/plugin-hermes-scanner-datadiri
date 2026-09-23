"""Evidence and completeness rules. No hiring scores or automated hiring decisions."""
import copy
import re
from datetime import date
from .storage import load
from .web import normalized, official_url

CHECK_STATUSES = {"memenuhi", "tidak_memenuhi", "belum_dapat_dinilai"}


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


def source_refs(root, manifest, refs, *, required=False, kinds=None):
    refs = records(refs, "source_refs")
    if required and not refs:
        raise ValueError("Bukti dokumen dan halaman wajib")
    docs = {doc["id"]: doc for doc in manifest["documents"]}
    for ref in refs:
        doc = docs.get(ref.get("document_id"))
        page = ref.get("page")
        if not doc or (kinds and doc["kind"] not in kinds):
            raise ValueError("Referensi dokumen tidak sesuai")
        state = load(root / "ocr" / f"{doc['id']}.json")
        if not state.get("success") or type(page) is not int or not 1 <= page <= state["page_count"]:
            raise ValueError("Referensi halaman di luar OCR berhasil")
        quote = require_text(ref.get("quote"), "quote")
        from pathlib import Path
        content = Path(state["markdown_files"][page-1]).read_text(encoding="utf-8")
        if normalized(quote) not in normalized(content):
            raise ValueError(f"Kutipan tidak ditemukan pada {doc['id']} halaman {page}")
    return refs


def validate_plan(root, manifest, payload):
    plan = copy.deepcopy(payload)
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
        source_refs(root, manifest, person.get("cv_refs", []), required=True, kinds={"cv"})
        inventory = records(person.get("certificate_inventory", []), "certificate_inventory")
        unique(inventory, "id", "certificate_inventory")
        for cert in inventory:
            source_refs(root, manifest, cert.get("source_refs", []), required=True)
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
        source_refs(root, manifest, requirement.get("source_refs", []), required=True, kinds={"kak", "addendum"})
    kak = plan.get("kak")
    if not isinstance(kak, dict):
        raise ValueError("kak wajib object metadata: title, version, package_id, analysis")
    require_text(kak.get("analysis"), "kak.analysis", 20)
    kak["status"] = "dokumen_diberikan_belum_diautentikasi" if any(d['kind'] == 'kak' for d in manifest['documents']) else "tidak_tersedia"
    # A matching public package can support provenance, never blanket legal validity.
    for rid in kak.get("receipt_ids", []):
        receipt = read_receipt(root, rid)
        identity = [kak.get("package_id", ""), kak.get("version", "")]
        if (receipt['success'] and receipt['evidence_kind'] == 'page' and receipt['urls'] and
                all(official_url(u) for u in receipt['urls']) and all(identity) and
                all(normalized(x) in normalized(receipt['content']) for x in identity)):
            kak["status"] = "identitas_paket_dan_versi_ditemukan_pada_sumber"
    coverage = records(plan.get("coverage"), "coverage")
    if any(c.get('document_id') not in {d['id'] for d in manifest['documents']} for c in coverage):
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
            if not targets and item.get("reason") not in {"blank", "cover", "unassigned", "unreadable"}:
                raise ValueError("Halaman tanpa personel memerlukan reason blank/cover/unassigned/unreadable")
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
    """Indicative union of calendar months; never silently infer a missing month/day."""
    all_months, relevant, supported, uncertain = set(), set(), set(), []
    for number, job in enumerate(history, 1):
        start, end = job.get("start_date", ""), job.get("end_date", "")
        if not all(isinstance(v, str) and re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", v) for v in (start, end)):
            uncertain.append(number)
            continue
        a, b = [int(v[:4]) * 12 + int(v[5:]) - 1 for v in (start, end)]
        if b < a:
            raise ValueError("Tanggal akhir pengalaman mendahului tanggal mulai")
        if as_of is not None:
            # Exclude future months and the unfinished assessment month; keep the
            # original dates for human review rather than fabricating exact days.
            cutoff = as_of.year * 12 + as_of.month - 2
            if b > cutoff:
                uncertain.append(number)
            b = min(b, cutoff)
        months = set(range(a, b+1))
        all_months |= months
        if job.get("relevant") is True:
            relevant |= months
            if job.get("supporting_refs"):
                supported |= months
    return {"calendar_months_unique": len(all_months), "relevant_months": len(relevant),
            "supported_relevant_months": len(supported), "uncertain_entries": uncertain,
            "method": "Bulan kalender inklusif, overlap dihitung sekali; indikator, bukan putusan KAK. Tanggal selain YYYY-MM tidak dihitung; bulan penilaian yang belum selesai dan bulan berikutnya dikecualikan."}


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
    doc_kinds = {d['id']: d['kind'] for d in manifest['documents']}

    def own_refs(refs):
        for ref in refs:
            if doc_kinds.get(ref.get('document_id')) in {'cv', 'attachment'} and not any(
                c['document_id'] == ref['document_id'] and person['id'] in c.get('person_ids', []) and
                c['first_page'] <= ref['page'] <= c['last_page'] for c in plan['coverage']
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
    required = {r['id']: r for r in plan['requirements'] if r['role'] == '*' or normalized(r['role']) == normalized(roster['role'])}
    checks = records(person.get('checks'), 'checks')
    if set(unique(checks, 'requirement_id', 'checks')) != set(required):
        raise ValueError("checks harus mencakup tepat semua persyaratan untuk role personel; jangan lewati kriteria")
    for check in checks:
        if check.get('status') not in CHECK_STATUSES:
            raise ValueError("Status check harus memenuhi/tidak_memenuhi/belum_dapat_dinilai")
        require_text(check.get('finding'), 'finding')
        require_text(check.get('analysis'), 'analysis', 30)
        source_refs(root, manifest, check.get('source_refs', []), required=check['status'] != 'belum_dapat_dinilai')
        if check['status'] == 'belum_dapat_dinilai':
            require_text(check.get('clarification'), 'clarification')
        check['requirement'] = required[check['requirement_id']]['text']
    history = records(person.get('employment_history', []), 'employment_history')
    for job in history:
        require_text(job.get('employer'), 'employer')
        source_refs(root, manifest, job.get('source_refs', []), required=True)
        source_refs(root, manifest, job.get('supporting_refs', []))
    person['chronology'] = chronology(history, date.fromisoformat(manifest['assessment_date']))
    certificates = records(person.get('certificates'), 'certificates')
    inventory = {c['id']: c for c in roster.get('certificate_inventory', [])}
    if set(unique(certificates, 'inventory_id', 'certificates')) != set(inventory):
        raise ValueError('certificates harus mencakup semua certificate_inventory, tanpa tambahan atau duplikat')
    for cert in certificates:
        if cert.get('source_refs') != inventory[cert['inventory_id']]['source_refs']:
            raise ValueError('Bukti sertifikat harus sama dengan inventory plan')
    if not certificates:
        require_text(person.get('certificate_limitation'), 'certificate_limitation')
    person['certificates'] = [certificate_result(root, manifest, c, person['name'], date.fromisoformat(manifest['assessment_date'])) for c in certificates]
    findings = person.get('findings', [])
    if not isinstance(findings, list) or any(not isinstance(x, str) for x in findings):
        raise ValueError("findings harus array teks")
    employers = records(person.get('employer_checks', []), 'employer_checks')
    if {normalized(j['employer']) for j in history} != {normalized(j.get('employer', '')) for j in employers}:
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
    person['overall'] = ('tidak_ada_kriteria_KAK' if not checks else
                         'ada_kriteria_tidak_memenuhi' if any(c['status'] == 'tidak_memenuhi' for c in checks) else
                         'perlu_klarifikasi' if any(c['status'] == 'belum_dapat_dinilai' for c in checks) else
                         'kriteria_diperiksa_memenuhi')
    person['review_note'] = 'Hasil bantu pemeriksaan dokumen; bukan keputusan menerima/menolak personel.'
    return person
