#!/usr/bin/env python3
"""Holt Vorschaubilder (Thumbnails) zu den gespeicherten Videolinks.

Die Bilder werden **nicht** heruntergeladen, sondern nur ihre URLs ermittelt
und in ``data/thumbs.json`` zwischengespeichert. Die Website bindet sie direkt
vom Originalanbieter ein (Hotlink), das Repo bleibt dadurch bildfrei.

Ablauf:
1. Alle Links aus den Lesezeichen sammeln (ueber ``erstelle_ordner.parse``).
2. Bereits bekannte URLs aus ``data/thumbs.json`` ueberspringen.
3. Fuer die restlichen Seiten die og:image-/twitter:image-Angabe auslesen.
4. Cache schreiben, sortiert – dadurch kleine, gut lesbare Diffs.

Das Skript ist auf vielen Requests ausgelegt und laeuft deshalb im
GitHub-Actions-Runner (oder lokal mit Internetzugang). Es ist idempotent:
ein zweiter Lauf holt nur, was noch fehlt.

Aufrufe:
    python3 tools/thumbnails.py                 # fehlende Bilder nachladen
    python3 tools/thumbnails.py --limit 50      # nur 50 Seiten (Test)
    python3 tools/thumbnails.py --refresh       # alles neu holen
    python3 tools/thumbnails.py --workers 4     # weniger parallel
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import erstelle_ordner as eo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "thumbs.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(r"""([a-zA-Z:-]+)\s*=\s*("([^"]*)"|'([^']*)')""")
OG_KEYS = {
    "og:image",
    "og:image:url",
    "og:image:secure_url",
    "twitter:image",
    "twitter:image:src",
    "image",
}

_lock = threading.Lock()


def tag_attrs(tag: str) -> dict[str, str]:
    return {
        m.group(1).lower(): html.unescape(m.group(3) if m.group(3) is not None else m.group(4))
        for m in ATTR_RE.finditer(tag)
    }


def extract_thumb(page: str, base: str | None = None) -> str | None:
    """Sucht die Vorschaubild-URL in einer HTML-Seite.

    Relative Angaben (``/img/x.jpg``) werden gegen ``base`` aufgeloest.
    """
    # 1) og:image / twitter:image (Reihenfolge der Attribute ist beliebig)
    for tag in META_TAG_RE.findall(page):
        attrs = tag_attrs(tag)
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in OG_KEYS and attrs.get("content"):
            return normalize_url(attrs["content"], base)

    # 2) <link rel="image_src" href="...">
    for tag in LINK_TAG_RE.findall(page):
        attrs = tag_attrs(tag)
        if "image_src" in (attrs.get("rel") or "").lower() and attrs.get("href"):
            return normalize_url(attrs["href"], base)

    return None


def normalize_url(url: str, base: str | None = None) -> str | None:
    url = url.strip()
    if not url or url.startswith("data:"):
        return None
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        if base:
            url = urljoin(base, url)
        else:
            return None
    return url if url.startswith(("http://", "https://")) else None


def fetch_thumb(url: str, timeout: float) -> str | None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(400_000)
            charset = response.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return None
    try:
        page = raw.decode(charset, errors="replace")
    except LookupError:
        page = raw.decode("utf-8", errors="replace")
    return extract_thumb(page, url)


def load_cache() -> dict[str, str]:
    if not CACHE.is_file():
        return {}
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v.startswith("http")}


def save_cache(thumbs: dict[str, str]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    ordered = {k: thumbs[k] for k in sorted(thumbs)}
    CACHE.write_text(
        json.dumps(ordered, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def collect_urls() -> list[str]:
    sources = sorted(eo.SOURCE_DIR.glob("*.md"))
    if not sources:
        return []
    entries = eo.parse(sources)
    urls = {url for entry in entries.values() for url in entry["links"]}
    return sorted(urls)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="max. Seiten pro Lauf")
    parser.add_argument("--workers", type=int, default=8, help="parallele Requests")
    parser.add_argument("--timeout", type=float, default=12.0, help="Timeout je Seite")
    parser.add_argument(
        "--max-seconds", type=float, default=600.0, help="Zeitbudget pro Lauf"
    )
    parser.add_argument("--refresh", action="store_true", help="Cache ignorieren")
    args = parser.parse_args(argv)

    urls = collect_urls()
    if not urls:
        print("Keine Links gefunden.", file=sys.stderr)
        return 1

    cache = {} if args.refresh else load_cache()
    pending = [u for u in urls if u not in cache]
    if args.limit:
        pending = pending[: args.limit]

    print(
        f"{len(urls)} Links, {len(cache)} im Cache, "
        f"{len(pending)} werden geholt (workers={args.workers})"
    )
    if not pending:
        save_cache(cache)
        return 0

    started = time.monotonic()
    found = failed = skipped = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(fetch_thumb, url, args.timeout): url for url in pending}
        for done, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            if time.monotonic() - started > args.max_seconds:
                skipped = len(pending) - done
                future.cancel()
                print(f"Zeitbudget erreicht – {skipped} Seiten bleiben offen.")
                break
            thumb = future.result()
            if thumb:
                with _lock:
                    cache[url] = thumb
                found += 1
            else:
                failed += 1
            if done % 50 == 0:
                print(f"  {done}/{len(pending)} – {found} Bilder, {failed} ohne Treffer")

    save_cache(cache)
    print(
        f"Fertig: {found} neue Bilder, {failed} ohne Treffer, "
        f"{len(cache)} im Cache von {len(urls)} Links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
