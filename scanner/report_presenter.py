"""Read-only presentation boundary shared by the BD PDF and workbook.

The saved review snapshot remains the source of truth. This module translates
labels and explanations; it never computes a status or changes evidence.
"""
import logging
import re
from .report_labels import (
    ANOMALY_LABELS, AUDIT_LABELS, DUPLICATE_LABELS, FIELD_LABELS, KIND_LABELS,
    NARRATIVE_TERMS, PRECISION_LABELS, SENTENCE_LABELS, STATUS_LABELS,
)

_LOG = logging.getLogger(__name__)
_LITERAL_KEYS = {
    'name', 'title', 'project', 'employer', 'role', 'client', 'consultant',
    'contractor', 'represented_organization', 'institution', 'major', 'degree',
    'holder', 'issuer', 'scheme', 'number', 'quote', 'requirement_text', 'url',
}


def _lookup(value, labels, fallback):
    if value in (None, ''):
        return fallback
    if value not in labels:
        _LOG.warning('Unmapped report label: %s', value)
    return labels.get(value, fallback)


def _substituter(labels):
    if not labels:
        return lambda text: text
    # Match whole identifiers/terms, longest first. Never replace substrings in names.
    lookup = {key.casefold(): value for key, value in labels.items()}
    pattern = re.compile(r'(?<!\w)(?:' + '|'.join(
        re.escape(key) for key in sorted(labels, key=len, reverse=True)
    ) + r')(?!\w)', re.IGNORECASE)
    return lambda text: pattern.sub(lambda m: lookup[m.group().casefold()], text)


class ReportPresenter:
    def __init__(self, data):
        self.documents = {d['id']: d.get('name') or 'Dokumen tanpa nama' for d in data.get('documents', [])}
        self.requirements = {r['id']: chr(34) + r['text'] + chr(34) for r in data.get('requirements', [])}
        self.people = {p['id']: p.get('name') or 'Personel tanpa nama' for p in data.get('people', [])}
        self.web_sources = {s['id']: f"Sumber daring {i}" for i, s in enumerate(data.get('sources', []), 1)}
        literals = set()

        def collect(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in _LITERAL_KEYS and isinstance(item, str) and item.strip():
                        literals.add(item)
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)
        collect(data)
        self._protected = re.compile(r'(?<!\w)(?:' + '|'.join(
            re.escape(x) for x in sorted(literals, key=len, reverse=True)
        ) + r')(?!\w)') if literals else None
        self._term_labels = {**NARRATIVE_TERMS, **FIELD_LABELS,
                             **{k: v for k, v in STATUS_LABELS.items() if '_' in k},
                             **AUDIT_LABELS, **self.documents, **self.people, **self.web_sources, **self.requirements}
        self._terms = _substituter(self._term_labels)

    @staticmethod
    def audit_label(code):
        return _lookup(code, AUDIT_LABELS, 'Pemeriksaan tambahan; perlu ditinjau')

    @staticmethod
    def status(value, applicable=True):
        if applicable is False:
            # This describes execution only. It does not claim that KAK has no requirement.
            return 'Tidak diterapkan'
        return _lookup(value, STATUS_LABELS, 'Belum dapat ditampilkan; perlu ditinjau')

    @staticmethod
    def field(value):
        return _lookup(value, FIELD_LABELS, 'Informasi lain; perlu ditinjau')

    @staticmethod
    def kind(value):
        return _lookup(value, KIND_LABELS, 'Jenis belum diketahui')

    @staticmethod
    def flag(value):
        return 'Ya' if value is True else 'Tidak' if value is False else 'Belum ditentukan'

    @staticmethod
    def precision(value):
        return _lookup(value, PRECISION_LABELS, 'Ketelitian tanggal belum diketahui')

    @staticmethod
    def duplicate(value):
        return _lookup(value, DUPLICATE_LABELS, 'Dugaan pencatatan ganda; perlu ditinjau')

    @staticmethod
    def anomaly_label(code):
        if str(code).startswith('period_'):
            return 'Periode pengalaman perlu diperiksa'
        return _lookup(code, ANOMALY_LABELS, 'Informasi perlu diperiksa kembali')

    def document(self, document_id):
        return self.documents.get(document_id, 'Dokumen belum teridentifikasi')

    def web_source(self, receipt_id):
        return self.web_sources.get(receipt_id, 'Sumber daring belum teridentifikasi')

    def references(self, values):
        # Quotes are evidence, not narrative: no glossary or rewriting is applied.
        return '\n'.join(f"{self.document(r.get('document_id'))}, halaman {r.get('page', '?')}: {r.get('quote', '')}"
                         for r in values or [])

    @staticmethod
    def experience(person, experience_id):
        for index, job in enumerate(person.get('employment_history', []), 1):
            if job.get('id') == experience_id:
                title = job.get('project') or f'Pengalaman {index} (nama proyek belum tersedia)'
                return f"{title} | {job.get('employer') or 'Perusahaan belum tersedia'} | {job.get('role') or 'Jabatan belum tersedia'} | {job.get('start_date') or '?'} s.d. {job.get('end_date') or '?'}"
        _LOG.warning('Unresolved report experience: %s', experience_id)
        return 'Pengalaman belum teridentifikasi; perlu ditinjau'

    def experiences(self, person, ids):
        return '\n'.join(self.experience(person, value) for value in ids or [])

    def uncertain_experiences(self, person):
        history = person.get('employment_history', [])
        labels = []
        for number in person.get('chronology', {}).get('uncertain_entries', []):
            if type(number) is int and 1 <= number <= len(history):
                labels.append(self.experience(person, history[number - 1].get('id')))
            else:
                labels.append('Periode belum teridentifikasi; perlu ditinjau')
        return '\n'.join(labels)

    def narrative(self, value, person=None):
        """Translate authored explanations, while protecting literal source values."""
        if value is None:
            return ''
        text = str(value)
        terms = _substituter({**self._term_labels, **{
            job['id']: self.experience(person, job['id'])
            for job in person.get('employment_history', []) if job.get('id')
        }}) if person else self._terms

        def translate(part):
            for old, new in SENTENCE_LABELS.items():
                part = part.replace(old, new)
            part = re.sub(
                r'Cross-check CV vs dokumen pendukung menemukan (\d+) konflik dan (\d+) field/bukti yang belum lengkap\.',
                lambda m: f'Ditemukan {m[1]} perbedaan informasi antara CV dan dokumen pendukung. '
                          f'Sebanyak {m[2]} butir informasi belum dapat dicocokkan dengan bukti yang tersedia. '
                          'Jumlah ini bukan jumlah dokumen yang harus dilengkapi.', part)
            part = re.sub(r'Hasil agregat (.*?); lihat kak_match_details untuk analisis per requirement\.',
                          'Rincian setiap persyaratan dan buktinya disajikan pada bagian Pemeriksaan KAK Terperinci.', part)
            part = re.sub(r'Ditemukan (\d+) anomali/isu data; (\d+) dikategorikan material untuk klarifikasi\.',
                          lambda m: f'{m[1]} hal memerlukan pemeriksaan kembali. '
                                    f'{m[2]} di antaranya ditandai penting untuk klarifikasi.', part)
            # One substitution pass: inserted source names/requirement text are not reprocessed.
            return terms(part)

        if not self._protected:
            return translate(text)
        chunks, start = [], 0
        for match in self._protected.finditer(text):
            chunks.extend((translate(text[start:match.start()]), match.group()))
            start = match.end()
        chunks.append(translate(text[start:]))
        return ''.join(chunks)

    def check(self, check, person=None):
        finding = self.narrative(check.get('finding', ''), person)
        analysis = self.narrative(check.get('analysis', ''), person)
        if check.get('applicable') is False and check.get('code') in {
            'position_experience_match', 'project_kak_match', 'organization_role_match',
            'experience_duration_match', 'responsibility_position_match', 'education_major_match',
            'certificate_kak_validity', 'technical_competency_match',
        }:
            finding = 'Belum ada persyaratan terkait aspek ini yang tersedia untuk pemeriksaan.'
            analysis = ('Penilaian aspek ini tidak dijalankan pada hasil pemeriksaan ini. '
                        'Hal ini tidak menyatakan bahwa KAK pasti tidak mensyaratkannya. '
                        'Periksa kembali kelengkapan dan keterbacaan KAK.')
        return {
            'label': self.audit_label(check['code']) if check.get('code') else 'Pemeriksaan persyaratan KAK',
            'status': self.status(check.get('status'), check.get('applicable', True)),
            'finding': finding, 'analysis': analysis,
            'clarification': self.narrative(check.get('clarification', ''), person),
            'evidence': self.references(check.get('source_refs', [])),
            'kak_evidence': self.references(check.get('kak_refs', [])),
        }

    def supporting_facts(self, values):
        lines = []
        for fact in values or []:
            fields = [f'{self.field(key)}: {fact[key]}' for key in (
                'project', 'employer', 'role', 'client', 'consultant', 'contractor',
                'represented_organization', 'start_date', 'end_date') if fact.get(key)]
            evidence = self.references(fact.get('source_refs', []))
            lines.append('\n'.join(fields + ([evidence] if evidence else [])))
        return '\n\n'.join(lines)
