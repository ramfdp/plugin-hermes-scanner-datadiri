"""Auditable dispatch to Hermes web/browser tools, without an extra crawler or API key."""
import inspect
import ipaddress
import json
import os
import re
import uuid
from urllib.parse import urlsplit
from .storage import locked, load, save, now, event

PORTALS = {"bnsp": "https://bnsp.go.id/check-certification", "konstruksi": "https://sijkt.pu.go.id/"}
TOOLS = {"web_search", "web_extract", "browser_navigate", "browser_snapshot", "browser_click", "browser_type"}


def normalized(value):
    return " ".join(str(value).casefold().split())


def public_url(url):
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip('.')
    if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    if '.' not in host or host.endswith((".local", ".internal", ".localhost")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def official_url(url):
    if not public_url(url):
        return False
    host = urlsplit(url).hostname.lower()
    configured = [x.strip().lower() for x in os.environ.get("HERMES_SCANNER_ISSUER_HOSTS", "").split(',') if x.strip()]
    return host.endswith('.go.id') or host in configured


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def response_urls(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"url", "sourceURL", "source_url", "page_url", "final_url"} and public_url(item):
                yield item
            else:
                yield from response_urls(item)
    elif isinstance(value, list):
        for item in value:
            yield from response_urls(item)


def is_failure(value):
    if isinstance(value, dict):
        if value.get("success") is False or value.get("isError") is True or value.get("error"):
            return True
        return any(is_failure(v) for v in value.values() if isinstance(v, (dict, list)))
    if isinstance(value, list):
        return any(is_failure(v) for v in value)
    return False


def validate_request(tool, arguments, purpose, manifest, plan):
    if tool not in TOOLS or not isinstance(arguments, dict):
        raise ValueError("Tool web tidak didukung")
    if purpose not in ("certificate", "kak", "employer"):
        raise ValueError("purpose harus certificate, kak, atau employer")
    if not manifest.get("allow_web"):
        raise ValueError("WEB_NOT_AUTHORIZED: pemeriksaan daring tidak diizinkan untuk run ini")
    encoded = json.dumps(arguments, ensure_ascii=False)
    if len(encoded) > 4000 or re.search(r"(?<!\d)\d{16}(?!\d)|[A-Za-z]:\\|file://|@\w+\.\w+", encoded):
        raise ValueError("WEB_PRIVACY_GUARD: jangan kirim NIK, kontak, path lokal, atau dokumen")
    if tool == "web_search":
        query = arguments.get("query", "")
        if not isinstance(query, str) or not query.strip() or len(query) > 300:
            raise ValueError("query pencarian wajib, maksimal 300 karakter")
        if any(normalized(p["name"]) in normalized(query) for p in plan.get("roster", [])):
            raise ValueError("WEB_PRIVACY_GUARD: nama kandidat tidak boleh ke mesin pencari")
        if set(arguments) - {"query", "limit"}:
            raise ValueError("web_search hanya menerima query dan limit")
        if not isinstance(arguments.get("limit", 5), int) or not 1 <= arguments.get("limit", 5) <= 5:
            raise ValueError("limit pencarian harus 1..5")
    urls = []
    if tool == "web_extract":
        urls = arguments.get("urls", [])
        if not isinstance(urls, list) or len(urls) != 1:
            raise ValueError("web_extract: satu URL per receipt agar sumber tidak tercampur")
    elif tool == "browser_navigate":
        urls = [arguments.get("url", "")]
    for url in urls:
        if not public_url(url) or (purpose != "employer" and not official_url(url)):
            raise ValueError("URL harus HTTPS publik; KAK/sertifikat hanya portal pemerintah atau issuer yang dikonfigurasi")
    if tool == "browser_type":
        value = arguments.get("text", "")
        if not isinstance(value, str) or not re.fullmatch(r"[\w ./:-]{1,100}", value):
            raise ValueError("Browser hanya boleh mengisi nomor sertifikat, bukan CV atau kredensial")
    return urls


async def lookup(ctx, args):
    run_id = args.get("run_id")
    tool, arguments, purpose = args.get("tool"), args.get("arguments", {}), args.get("purpose")
    with locked(run_id) as root:
        manifest = load(root / "manifest.json")
        plan = load(root / "plan.json") if (root / "plan.json").exists() else {}
        requested_urls = validate_request(tool, arguments, purpose, manifest, plan)
        if tool in {"browser_snapshot", "browser_click", "browser_type"}:
            state = load(root / "browser.json") if (root / "browser.json").exists() else {}
            if not official_url(state.get("url", "")):
                raise ValueError("Navigasikan portal resmi melalui scanner_web_lookup terlebih dahulu")
        if len(list((root / 'web').glob('*.json'))) >= 200:
            raise ValueError('WEB_REQUEST_LIMIT: maksimal 200 receipt per run')
        receipt_id = "W" + uuid.uuid4().hex[:16]
        started = now()
        try:
            if not callable(getattr(ctx, "dispatch_tool", None)):
                raise RuntimeError("WEB_DISPATCH_UNAVAILABLE: versi Hermes memerlukan ctx.dispatch_tool")
            raw = ctx.dispatch_tool(tool, arguments)
            if inspect.isawaitable(raw):
                raw = await raw
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except ValueError:
                    raw = {"content": raw}
            # Tool receipts contain actual tool results, never a caller-supplied quote.
            content = "\n".join(strings(raw))
            urls = sorted(set(response_urls(raw)))
            # web_extract on a single URL can omit URL metadata. Browser receipts cannot.
            if tool == "web_extract" and not urls:
                urls = requested_urls
            success = bool(content.strip()) and not is_failure(raw)
            if tool.startswith("browser_") and urls:
                save(root / "browser.json", {"url": urls[0], "at": now()})
            if tool.startswith("browser_") and not all(official_url(url) for url in urls):
                success = False
            receipt = {"id": receipt_id, "tool": tool, "purpose": purpose, "started_at": started,
                       "checked_at": now(), "success": success, "urls": urls, "content": content,
                       "raw": raw, "evidence_kind": "page" if tool in {"web_extract", "browser_snapshot"} else "discovery"}
        except Exception as exc:
            receipt = {"id": receipt_id, "tool": tool, "purpose": purpose, "started_at": started,
                       "checked_at": now(), "success": False, "urls": [], "content": "",
                       "error": type(exc).__name__, "message": str(exc), "evidence_kind": "unavailable"}
        save(root / "web" / f"{receipt_id}.json", receipt)
        event(root, "web", success=receipt["success"], receipt_id=receipt_id, tool=tool)
        # Response is bounded but the receipt remains complete locally, with an explicit continuation.
        text = receipt["content"]
        return {"success": receipt["success"], "receipt_id": receipt_id, "checked_at": receipt["checked_at"],
                "urls": receipt["urls"], "evidence_kind": receipt["evidence_kind"], "content": text[:16000],
                "truncated": len(text) > 16000, "error": receipt.get("error"), "message": receipt.get("message"),
                "next": "scanner_review action=read_receipt, payload={receipt_id,offset}" if len(text) > 16000 else None}


def make_handler(ctx):
    async def handler(args, **kwargs):
        try:
            result = await lookup(ctx, args)
        except Exception as exc:
            result = {"success": False, "error": type(exc).__name__, "message": str(exc)}
        return json.dumps(result, ensure_ascii=False)
    return handler
