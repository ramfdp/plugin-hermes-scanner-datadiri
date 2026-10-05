"""Indonesian display vocabulary. Internal evaluation values are never changed."""

AUDIT_LABELS = {
    'position_experience_match': 'Kesesuaian posisi dengan pengalaman',
    'project_kak_match': 'Kesesuaian proyek dengan KAK',
    'organization_role_match': 'Kesesuaian perusahaan dan peran dalam proyek',
    'project_period_accuracy': 'Ketepatan periode pengalaman',
    'experience_duration_match': 'Kecukupan lama pengalaman',
    'responsibility_position_match': 'Kesesuaian tugas dengan jabatan',
    'education_major_match': 'Kesesuaian pendidikan dan jurusan',
    'certificate_kak_validity': 'Kesesuaian sertifikat dan masa berlaku',
    'identity_consistency': 'Konsistensi informasi pengalaman',
    'project_overlap': 'Pengalaman dengan periode bersamaan',
    'project_duplicate': 'Pemeriksaan pencatatan pengalaman ganda',
    'technical_competency_match': 'Kesesuaian kompetensi teknis',
    'cv_supporting_document_match': 'Kesesuaian CV dengan dokumen pendukung',
    'data_anomaly': 'Informasi yang perlu diperiksa kembali',
    'kak_conclusion': 'Kesimpulan pemenuhan KAK',
}

STATUS_LABELS = {
    'memenuhi': 'Memenuhi', 'tidak_memenuhi': 'Tidak Memenuhi',
    'perlu_klarifikasi': 'Perlu Klarifikasi',
    'belum_dapat_dinilai': 'Belum dapat dinilai',
    'terverifikasi': 'Terverifikasi', 'sebagian_terverifikasi': 'Sebagian terverifikasi',
    'belum_dapat_diverifikasi': 'Belum dapat diverifikasi',
    'tidak_ditemukan': 'Tidak ditemukan pada sumber yang diperiksa',
    'tidak_diketahui': 'Belum diketahui', 'tidak_tersedia': 'Belum tersedia',
    'kedaluwarsa': 'Sudah melewati tanggal akhir', 'belum_berlaku': 'Belum mulai berlaku',
    'belum_melewati_tanggal_akhir': 'Belum melewati tanggal akhir pada dokumen',
    'dokumen_diberikan_belum_diautentikasi': 'Dokumen tersedia; keasliannya belum dikonfirmasi',
    'identitas_paket_dan_versi_ditemukan_pada_sumber': 'Identitas paket dan versi ditemukan pada sumber daring',
    'match': 'Sesuai', 'conflict': 'Berbeda; perlu dikonfirmasi',
    'missing_support': 'Bukti pendukung belum tersedia untuk informasi ini',
    'support_does_not_show_value': 'Informasi belum ditemukan pada dokumen pendukung',
    'cv_does_not_show_value': 'Informasi belum ditemukan pada CV',
}

FIELD_LABELS = {
    'project': 'Nama proyek', 'employer': 'Perusahaan', 'role': 'Jabatan',
    'client': 'Pemberi kerja', 'consultant': 'Konsultan', 'contractor': 'Kontraktor',
    'represented_organization': 'Instansi yang diwakili',
    'start_date': 'Tanggal mulai', 'end_date': 'Tanggal selesai',
    'level': 'Jenjang', 'degree': 'Gelar', 'major': 'Jurusan', 'institution': 'Institusi',
    'certificate_summary': 'Sertifikat yang disebutkan dalam CV',
    'education': 'Pendidikan', 'education_records': 'Riwayat pendidikan',
    'employment_history': 'Riwayat pengalaman', 'supporting_facts': 'Informasi pada dokumen pendukung',
    'claimed_months': 'Lama pengalaman yang tercantum dalam CV',
    'responsibilities': 'Uraian tugas', 'holder': 'Pemegang sertifikat',
    'issuer': 'Penerbit sertifikat', 'scheme': 'Bidang sertifikat',
    'issued_on': 'Tanggal terbit', 'expires_on': 'Tanggal akhir berlaku',
}

KIND_LABELS = {
    'cv': 'CV', 'kak': 'KAK', 'addendum': 'Adendum', 'attachment': 'Dokumen pendukung',
    'unknown': 'Jenis dokumen belum diketahui', 'experience': 'Pengalaman proyek',
    'education': 'Pendidikan', 'certificate': 'Sertifikat', 'other': 'Dokumen lain',
    'reference': 'Dokumen acuan', 'unassigned': 'Belum dikaitkan dengan personel',
    'unreadable': 'Belum terbaca',
}

ANOMALY_LABELS = {
    'consistency_conflict': 'Perbedaan informasi pengalaman',
    'consistency_missing': 'Informasi pengalaman belum dapat dicocokkan',
    'experience_overlap': 'Periode pengalaman bersamaan',
    'experience_duplicate_exact': 'Pencatatan pengalaman yang sama',
    'experience_duplicate_possible': 'Dugaan pencatatan pengalaman ganda',
    'cv_support_conflict': 'Perbedaan antara CV dan dokumen pendukung',
    'cv_support_missing': 'Bukti pendukung belum cukup',
    'claimed_duration_mismatch': 'Perbedaan lama pengalaman',
}

PRECISION_LABELS = {
    'exact_day': 'Tanggal lengkap tersedia',
    'calendar_range_from_partial_dates': 'Perkiraan rentang; tanggal belum lengkap',
    'day': 'Tanggal lengkap', 'month': 'Bulan dan tahun', 'year': 'Tahun saja',
}
DUPLICATE_LABELS = {'exact': 'Pencatatan pengalaman yang sama', 'possible': 'Dugaan pencatatan ganda'}

# These are complete, known engine sentences, not replacements in source evidence.
SENTENCE_LABELS = {
    'Tidak ditemukan duplikasi exact maupun kandidat duplikasi pengalaman.':
        'Tidak ditemukan indikasi pengalaman proyek yang dicatat lebih dari sekali berdasarkan data yang tersedia.',
    'Overlap adalah fakta kronologi, bukan otomatis pelanggaran. Reviewer perlu memastikan apakah pekerjaan memang berjalan bersamaan dan bagaimana KAK memperlakukan periode tersebut.':
        'Periode pekerjaan yang bersamaan belum cukup untuk menyatakan pengalaman tidak memenuhi persyaratan. Pelaksanaan pekerjaan dan ketentuan KAK perlu dikonfirmasi.',
    'Konfirmasi proyek yang berjalan bersamaan dan periode yang belum valid; jangan menghapus pengalaman hanya karena overlap.':
        'Konfirmasi pelaksanaan proyek yang waktunya bersamaan dan lengkapi tanggal yang belum jelas. Pengalaman tidak otomatis dihapus karena periodenya bersamaan.',
    'Seluruh pasangan pengalaman dengan periode valid dibandingkan sebagai rentang kalender inklusif.':
        'Periode pengalaman dibandingkan dengan menyertakan tanggal mulai dan tanggal selesai.',
    'Cross-check membandingkan field terstruktur tanpa menganggap dokumen yang berbeda sebagai bukti pemalsuan.':
        'Informasi pada CV dibandingkan dengan dokumen pendukung. Perbedaan informasi tidak dengan sendirinya membuktikan pemalsuan.',
    'Data terstruktur yang dapat dicross-check konsisten antara CV dan dokumen pendukung.':
        'Informasi yang dapat dibandingkan sesuai antara CV dan dokumen pendukung.',
    'Durasi memakai union bulan kalender pengalaman yang ditandai relevan; overlap tidak dihitung dua kali.':
        'Lama pengalaman dihitung dari bulan kalender yang relevan. Bulan dengan beberapa pekerjaan bersamaan hanya dihitung satu kali.',
    'Jenjang dibandingkan dengan urutan pendidikan; jurusan hanya dianggap exact bila normalisasinya sama dengan accepted_majors KAK.':
        'Jenjang pendidikan dibandingkan dengan syarat KAK. Nama jurusan harus sesuai setelah perbedaan cara penulisan diseragamkan; kesetaraan jurusan yang berbeda masih perlu dikonfirmasi.',
    'Belum ada education_records terstruktur untuk membandingkan pendidikan dengan KAK.':
        'Informasi pendidikan belum tersedia untuk dibandingkan dengan KAK.',
    'Kesimpulan final dihitung deterministik: Tidak Memenuhi mengalahkan Klarifikasi; Klarifikasi mengalahkan Memenuhi. Tidak ada KAK tidak pernah dianggap Memenuhi.':
        'Persyaratan yang tidak terpenuhi menentukan hasil Tidak Memenuhi. Jika masih ada hal yang belum jelas, hasilnya Perlu Klarifikasi. Tanpa KAK, pemenuhan tidak dapat disimpulkan.',
    'Tidak ada data terstruktur yang cukup untuk menjalankan anomaly engine.':
        'Informasi yang tersedia belum cukup untuk memeriksa ketidaksesuaian data.',
}

# Applied only to authored explanations, never to names, requirement text or quotations.
NARRATIVE_TERMS = {
    'field/bukti': 'butir informasi yang belum didukung bukti',
    'dicross-check': 'dicocokkan', 'cross-check': 'pencocokan',
    'requirement': 'persyaratan', 'requirements': 'persyaratan',
    'field': 'butir informasi', 'fields': 'butir informasi',
    'overlap': 'periode bersamaan', 'exact': 'sama', 'duplicate': 'pencatatan ganda',
    'possible': 'dugaan', 'reviewer': 'pemeriksa', 'review': 'pemeriksaan',
    'matching': 'pencocokan', 'structured': 'yang tercatat', 'terstruktur': 'yang tercatat',
    'evidence': 'bukti', 'assessment': 'penilaian', 'semantic': 'berdasarkan isi dokumen',
    'semantik': 'berdasarkan isi dokumen', 'server-side': 'oleh sistem',
    'backend': 'sistem', 'deterministik': 'berdasarkan aturan pemeriksaan',
    'anomaly engine': 'pemeriksaan ketidaksesuaian data',
    'normalisasi': 'penyeragaman penulisan', 'presisi': 'ketelitian tanggal',
    'parameter': 'ketentuan', 'accepted_majors': 'jurusan yang disyaratkan dalam KAK',
    'kak_match_details': 'rincian pemeriksaan KAK', 'source_refs': 'rujukan dokumen',
    'kak_refs': 'rujukan KAK', 'receipt_id': 'rujukan pemeriksaan daring', 'receipt': 'catatan pemeriksaan daring',
    'atomik': 'per butir', 'engine': 'sistem pemeriksaan', 'union': 'gabungan',
    'anomali': 'hal yang perlu diperiksa', 'material': 'penting untuk klarifikasi',
    'roster': 'daftar personel', 'role': 'posisi', 'legacy': 'sebelumnya',
    'unassigned': 'belum dikaitkan dengan personel', 'unreadable': 'belum terbaca',
    'OCR': 'pembacaan otomatis dokumen', 'JSON': 'data kerja aplikasi',
}
