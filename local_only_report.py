import argparse
import re
from pathlib import Path

from exporter import render_daftar_tenaga_ahli


def field(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_ktp_markdown(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    tempat_tgl = field(text, r"Tempat/Tgl\s+Lahr\s*:\s*(.+)")
    return {
        "provinsi": field(text, r"^PROVINSI\s+(.+)$"),
        "kabupaten_kota": field(text, r"^KABUPATEN\s+(.+)$"),
        "nik": field(text, r"^NIK\s*:\s*(.+)$"),
        "nama": field(text, r"^Nama\s*:\s*(.+)$"),
        "tempat_tanggal_lahir": tempat_tgl,
        "jenis_kelamin": field(text, r"^Jenis Kelamin\s+(.+)$"),
        "golongan_darah": field(text, r"^Gol Darah\s*:\s*(.+)$"),
        "alamat": field(text, r"^Alamat\s*:\s*(.+)$"),
        "rt_rw": field(text, r"^RTRW\s+(.+)$"),
        "kelurahan_desa": field(text, r"^Ke/Desa\s*:\s*(.+)$"),
        "kecamatan": field(text, r"^Kecamatan\s*:\s*(.+)$"),
        "agama": field(text, r"^Agama\s*:\s*(.+)$"),
        "status_perkawinan": field(text, r"^Status Perkawinan\s*:\s*(.+)$"),
        "pekerjaan": field(text, r"^Pekerjaan\s*:\s*(.+)$"),
        "kewarganegaraan": field(text, r"^Kewarganegaraan\s*:\s*(.+)$"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Local-only OCR markdown to tenaga ahli XLSX")
    parser.add_argument("markdown", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if not args.markdown.is_file():
        raise SystemExit(f"OCR markdown tidak ditemukan: {args.markdown}")
    if args.output.suffix.lower() != ".xlsx":
        raise SystemExit("Output harus berformat .xlsx")

    ktp = parse_ktp_markdown(args.markdown.resolve())
    if not ktp["nama"] or not ktp["nik"]:
        raise SystemExit("Field Nama atau NIK tidak ditemukan pada hasil OCR lokal")

    payload = {
        "judul": "DAFTAR TENAGA AHLI",
        "wilayah": f"{ktp['provinsi']} - {ktp['kabupaten_kota']}",
        "pekerjaan": ktp["pekerjaan"],
        "personel": [{
            "nama_personel": ktp["nama"],
            "nik": ktp["nik"],
            "jabatan_personel": ktp["pekerjaan"],
            "kualifikasi_pendidikan": "",
            "sertifikat_keahlian": "",
            "pengalaman_min_kak_tahun": "",
            "pengalaman_kerja_bulan": "",
            "pengalaman_kerja_tahun": "",
        }],
    }

    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    render_daftar_tenaga_ahli(payload, args.output.resolve())
    print(f"LOCAL_ONLY_REPORT_CREATED={args.output.resolve()}")


if __name__ == "__main__":
    main()
