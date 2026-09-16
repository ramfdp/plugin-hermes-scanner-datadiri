import argparse
import json
import math
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import (
    Alignment,
    Border,
    Font,
    PatternFill,
    Side,
)
from openpyxl.worksheet.page import PageMargins


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


# ============================================================
# JSON
# ============================================================

def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"File JSON tidak ditemukan: {path}"
        )

    if path.stat().st_size == 0:
        raise ValueError(
            f"File JSON kosong: {path}"
        )

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON tidak valid pada '{path}' "
            f"baris {exc.lineno}, kolom {exc.colno}: "
            f"{exc.msg}"
        ) from exc


# ============================================================
# CALCULATION
# ============================================================

def truncate_decimal(
    value: float,
    decimals: int = 2,
) -> float:
    multiplier = 10 ** decimals

    return (
        math.floor(value * multiplier)
        / multiplier
    )


def calculate_years(months) -> float:
    try:
        months = float(months)
    except (TypeError, ValueError):
        return 0.0

    return truncate_decimal(
        months / 12,
        2,
    )


def format_indonesian_decimal(value) -> str:
    """
    6    -> 6,00
    3.16 -> 3,16
    5.5  -> 5,50
    """

    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""

    return (
        f"{number:.2f}"
        .replace(".", ",")
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_payload(
    payload: dict,
    schema: dict,
):
    missing = []

    for field in schema.get(
        "required_fields",
        [],
    ):
        if field not in payload:
            missing.append(field)

    if missing:
        raise ValueError(
            "Field wajib belum tersedia: "
            + ", ".join(missing)
        )

    personel = payload.get("personel")

    if not isinstance(personel, list):
        raise ValueError(
            "'personel' harus berupa array/list."
        )

    for key in ("personel", "employment_history"):
        records = payload.get(key, [])
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError(f"'{key}' harus berupa array object.")


# ============================================================
# EXCEL RENDERER
# ============================================================

def render_daftar_tenaga_ahli(
    payload: dict,
    output_path: Path,
):
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Daftar Tenaga Ahli"

    # --------------------------------------------------------
    # GLOBAL SETTINGS
    # --------------------------------------------------------

    sheet.sheet_view.showGridLines = False

    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4

    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0

    sheet.sheet_properties.pageSetUpPr.fitToPage = True

    sheet.page_margins = PageMargins(
        left=0.25,
        right=0.25,
        top=0.35,
        bottom=0.35,
        header=0.15,
        footer=0.15,
    )

    # --------------------------------------------------------
    # FONT
    # --------------------------------------------------------

    font_name = "Century Gothic"

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title_data = [
        (
            1,
            payload.get(
                "judul",
                "DAFTAR TENAGA AHLI",
            ),
            11,
        ),

        (
            2,
            payload.get(
                "wilayah",
                "",
            ),
            10,
        ),

        (
            3,
            payload.get(
                "pekerjaan",
                "",
            ),
            10,
        ),
    ]

    for row, text, size in title_data:

        sheet.merge_cells(
            start_row=row,
            start_column=1,
            end_row=row,
            end_column=9,
        )

        cell = sheet.cell(
            row=row,
            column=1,
            value=text,
        )

        cell.font = Font(
            name=font_name,
            size=size,
            bold=True,
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
        )

    sheet.row_dimensions[1].height = 22
    sheet.row_dimensions[2].height = 21
    sheet.row_dimensions[3].height = 21

    # Spasi seperti screenshot
    sheet.row_dimensions[4].height = 10

    # --------------------------------------------------------
    # TABLE HEADER
    # --------------------------------------------------------

    header_row = 5

    headers = [
        "No",
        "Nama Personel",
        "NIK",
        "Jabatan Personel",
        "Kualifikasi\nPendidikan",
        "Sertifikat Keahlian",
        "Pengalaman min\ndalam KAK\n(Tahun)",
        "Pengalaman\nKerja (Bulan)",
        "Pengalaman\nKerja (Tahun)",
    ]

    # Biru mendekati screenshot
    header_fill = PatternFill(
        fill_type="solid",
        fgColor="8EA9D8",
    )

    black_side = Side(
        style="thin",
        color="000000",
    )

    all_border = Border(
        left=black_side,
        right=black_side,
        top=black_side,
        bottom=black_side,
    )

    for column, header in enumerate(
        headers,
        start=1,
    ):
        cell = sheet.cell(
            row=header_row,
            column=column,
            value=header,
        )

        cell.font = Font(
            name=font_name,
            size=8,
            bold=True,
            color="000000",
        )

        cell.fill = header_fill

        cell.border = all_border

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    sheet.row_dimensions[
        header_row
    ].height = 48

    # --------------------------------------------------------
    # COLUMN WIDTH
    # --------------------------------------------------------

    #
    # Proporsi dibuat mengikuti screenshot:
    #
    # No          kecil
    # Nama        sedang
    # NIK         cukup lebar
    # Jabatan     paling lebar
    # Pendidikan  sedang
    # Sertifikat  sedang
    #

    column_widths = {
        "A": 5,
        "B": 18,
        "C": 24,
        "D": 36,
        "E": 16,
        "F": 23,
        "G": 19,
        "H": 17,
        "I": 17,
    }

    for column, width in column_widths.items():
        sheet.column_dimensions[
            column
        ].width = width

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    personel = payload.get(
        "personel",
        [],
    )

    first_data_row = 6

    for number, person in enumerate(
        personel,
        start=1,
    ):
        row = (
            first_data_row
            + number
            - 1
        )

        months = person.get(
            "pengalaman_kerja_bulan",
            "",
        )

        # Jika tahun sudah diberikan Hermes,
        # gunakan nilainya.
        #
        # Kalau belum, hitung otomatis dari bulan.

        if (
            person.get(
                "pengalaman_kerja_tahun"
            )
            not in (None, "")
        ):
            years = person.get(
                "pengalaman_kerja_tahun"
            )

        elif months not in (None, ""):
            years = calculate_years(
                months
            )

        else:
            years = ""

        years_display = (
            format_indonesian_decimal(
                years
            )
            if years != ""
            else ""
        )

        min_kak = person.get(
            "pengalaman_min_kak_tahun",
            "",
        )

        if min_kak not in (
            None,
            "",
        ):
            min_kak_display = (
                f"{min_kak} Tahun"
            )
        else:
            min_kak_display = ""

        values = [
            number,

            person.get(
                "nama_personel",
                "",
            ),

            str(
                person.get(
                    "nik",
                    "",
                )
            ),

            person.get(
                "jabatan_personel",
                "",
            ),

            person.get(
                "kualifikasi_pendidikan",
                "",
            ),

            person.get(
                "sertifikat_keahlian",
                "",
            ),

            min_kak_display,

            months,

            years_display,
        ]

        for column, value in enumerate(
            values,
            start=1,
        ):
            cell = sheet.cell(
                row=row,
                column=column,
                value=value,
            )

            cell.border = all_border

            cell.font = Font(
                name=font_name,
                size=8,
            )

            # Nama dan NIK kiri.
            # Lainnya mengikuti screenshot,
            # mayoritas center.

            if column in (2, 3):

                cell.alignment = Alignment(
                    horizontal="left",
                    vertical="center",
                    wrap_text=True,
                )

            else:

                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )

        # ----------------------------------------------------
        # NIK HARUS TEXT
        # ----------------------------------------------------

        nik_cell = sheet.cell(
            row=row,
            column=3,
        )

        nik_cell.number_format = "@"

        # ----------------------------------------------------
        # MONTH
        # ----------------------------------------------------

        if isinstance(
            months,
            (int, float),
        ):
            sheet.cell(
                row=row,
                column=8,
            ).number_format = "0"

        # ----------------------------------------------------
        # ROW HEIGHT
        # ----------------------------------------------------

        sheet.row_dimensions[
            row
        ].height = 54

    # --------------------------------------------------------
    # PRINT AREA
    # --------------------------------------------------------

    if personel:

        last_row = (
            first_data_row
            + len(personel)
            - 1
        )

        sheet.print_area = (
            f"A1:I{last_row}"
        )

        sheet.auto_filter.ref = (
            f"A5:I{last_row}"
        )

    # --------------------------------------------------------
    # FREEZE
    # --------------------------------------------------------

    sheet.freeze_panes = "A6"

    # --------------------------------------------------------
    # ALIGN PAGE
    # --------------------------------------------------------

    sheet.print_options.horizontalCentered = True

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if "employment_history" in payload:
        history = workbook.create_sheet("Riwayat Pekerjaan")
        fields = ("nama_personel", "employer", "role", "start_date", "end_date",
                  "duration_months", "responsibilities", "project", "source_page", "source_quote")
        history.append(fields)
        for job in payload["employment_history"]:
            history.append([job.get(field, "") for field in fields])
        history.freeze_panes = "A2"
        history.auto_filter.ref = history.dimensions
        for column in history.columns:
            history.column_dimensions[column[0].column_letter].width = 24
            for cell in column:
                cell.alignment = Alignment(wrap_text=True, vertical="top")

    # OCR and mapped strings are data, including strings beginning with '='.
    for worksheet in workbook:
        for row in worksheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    workbook.save(output_path)


# ============================================================
# TEMPLATE DISPATCHER
# ============================================================

def export_template(
    template_id: str,
    payload_path: Path,
    output_path: Path,
):
    payload = load_json(
        payload_path
    )

    result = export_payload(
        template_id=template_id,
        payload=payload,
        output_path=output_path,
    )

    result["payload_file"] = str(
        payload_path.resolve()
    )

    return result


def export_payload(
    template_id: str,
    payload: dict,
    output_path: Path,
):
    if template_id != "daftar_tenaga_ahli":
        raise ValueError(f"Template tidak didukung: {template_id}")
    template_dir = (
        TEMPLATES_DIR
        / template_id
    )

    schema_path = (
        template_dir
        / "schema.json"
    )

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema template tidak ditemukan: "
            f"{schema_path}"
        )

    schema = load_json(
        schema_path
    )

    validate_payload(
        payload,
        schema,
    )

    if (
        template_id
        == "daftar_tenaga_ahli"
    ):

        render_daftar_tenaga_ahli(
            payload=payload,
            output_path=output_path,
        )

    else:

        raise ValueError(
            f"Renderer untuk template "
            f"'{template_id}' belum tersedia."
        )

    payload_file = output_path.with_suffix(".payload.json")
    payload_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    workbook = load_workbook(output_path, read_only=True, data_only=True)
    try:
        workbook_data = {
            sheet.title: list(sheet.iter_rows(min_row=5 if sheet.title == "Daftar Tenaga Ahli" else 1,
                                            values_only=True))
            for sheet in workbook
        }
    finally:
        workbook.close()

    return {
        "success": True,

        "payload_file": str(payload_file.resolve()),
        "workbook_data": workbook_data,

        "template": template_id,

        "output_file": str(
            output_path.resolve()
        ),

        "row_count": len(
            payload.get(
                "personel",
                [],
            )
        ),
    }


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Hermes document template exporter"
        )
    )

    parser.add_argument(
        "--template",
        required=True,
        help=(
            "Template ID. "
            "Contoh: daftar_tenaga_ahli"
        ),
    )

    payload_group = parser.add_mutually_exclusive_group(
        required=True
    )

    payload_group.add_argument(
        "--payload",
        help=(
            "Path file JSON hasil mapping Hermes"
        ),
    )

    payload_group.add_argument(
        "--payload-json",
        help="JSON hasil mapping Hermes, atau '-' untuk membaca stdin",
    )

    parser.add_argument(
        "--output",
        required=True,
        help=(
            "Path output Excel .xlsx"
        ),
    )

    args = parser.parse_args()

    try:

        if args.payload_json is not None:
            payload_text = (
                sys.stdin.read()
                if args.payload_json == "-"
                else args.payload_json
            )
            result = export_payload(
                template_id=args.template,
                payload=json.loads(payload_text),
                output_path=Path(args.output),
            )
        else:
            result = export_template(
                template_id=args.template,
                payload_path=Path(args.payload),
                output_path=Path(args.output),
            )

        print(
            "HERMES_EXPORT_RESULT="
            + json.dumps(
                result,
                ensure_ascii=False,
            )
        )

    except Exception as exc:

        result = {
            "success": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }

        print(
            "HERMES_EXPORT_RESULT="
            + json.dumps(
                result,
                ensure_ascii=False,
            )
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
