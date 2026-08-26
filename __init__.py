from . import schemas
from . import tools


def register(ctx):
    ctx.register_tool(
        name="scan_document_ocr",
        toolset="hermes_scanner",
        schema=schemas.SCAN_DOCUMENT_OCR,
        handler=tools.scan_document_ocr,
    )

    ctx.register_tool(
        name="export_document",
        toolset="hermes_scanner",
        schema=schemas.EXPORT_DOCUMENT,
        handler=tools.export_document,
    )
