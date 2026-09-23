"""Hermes loader entry point. Runtime implementation lives under scanner/."""
from .scanner import schemas, tools, web


def register(ctx):
    for contract, handler in (
        (schemas.SCAN_DOCUMENT_OCR, tools.scan_document_ocr),
        (schemas.EXPORT_DOCUMENT, tools.export_document),
        (schemas.EXPORT_CV_REPORT, tools.export_cv_report),
        (schemas.SCANNER_REVIEW, tools.scanner_review),
        (schemas.SCANNER_WEB_LOOKUP, web.make_handler(ctx)),
    ):
        ctx.register_tool(name=contract['name'], toolset='hermes_scanner', schema=contract, handler=handler)
