#!/usr/bin/env python3
"""Baut aus den Lesezeichen eine statische Website (fuer GitHub Pages) in ``docs/``.

Erzeugt:
  docs/index.html              Uebersicht mit Suche und Sortierung
  docs/p/<slug>/index.html     eine Seite pro Darstellerin
  docs/assets/style.css        gemeinsames Stylesheet
  docs/assets/app.js           Suche, Sortierung, Altersabfrage
  docs/videothek.html          alles in einer Datei (offline nutzbar)
  docs/robots.txt              kein Indexieren durch Suchmaschinen
  docs/.nojekyll               Dateien unveraendert ausliefern

Die Seite braucht keine Build-Tools: reines HTML/CSS/JS, kein Framework,
kein npm, kein Jekyll (deshalb auch ``docs/.nojekyll``).

Die Inhalte kommen aus derselben Quelle wie die Ordner
(``tools/erstelle_ordner.py``), damit Website und Ordner nie auseinanderlaufen.

Aufruf:
    python3 tools/build_site.py
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import erstelle_ordner as eo  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
SITE_TITLE = "Videothek"
SITE_DESC = "Persoenliche Sammlung von Videolinks, sortiert nach Darstellerin."

CSS = """
:root{
  --bg:#0d0f16; --bg-soft:#151926; --card:#1a1f2e; --card-hover:#222940;
  --line:#2a3145; --text:#e8ecf5; --muted:#8f9ab5; --accent:#ff5c8a;
  --accent-soft:rgba(255,92,138,.14); --radius:14px;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0; background:var(--bg); color:var(--text);
  font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.wrap{width:min(1180px,calc(100% - 2.5rem));margin-inline:auto}

/* Kopfbereich */
header.top{
  position:sticky;top:0;z-index:20;backdrop-filter:blur(12px);
  background:rgba(13,15,22,.82);border-bottom:1px solid var(--line);
}
header.top .wrap{display:flex;align-items:center;gap:1rem;padding:.85rem 0;flex-wrap:wrap}
.brand{font-weight:750;font-size:1.05rem;letter-spacing:.02em;color:var(--text)}
.brand span{color:var(--accent)}
.brand:hover{text-decoration:none;color:var(--text)}
.count{margin-left:auto;color:var(--muted);font-size:.85rem}
.back{margin-left:auto;font-size:.85rem}

/* Hero */
.hero{padding:3rem 0 1.5rem}
.hero h1{margin:0 0 .5rem;font-size:clamp(1.9rem,4.5vw,2.9rem);line-height:1.1;letter-spacing:-.02em}
.hero p{margin:0;color:var(--muted);max-width:62ch}
.stats{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:1.3rem}
.pill{
  border:1px solid var(--line);background:var(--bg-soft);color:var(--muted);
  border-radius:999px;padding:.35rem .8rem;font-size:.82rem
}
.pill b{color:var(--text);font-weight:650}

/* Steuerung */
.controls{display:flex;gap:.7rem;flex-wrap:wrap;margin:1.8rem 0 1.2rem;position:sticky;top:60px;z-index:10;
  background:linear-gradient(var(--bg) 70%,transparent);padding:.4rem 0 .8rem}
input[type=search]{
  flex:1 1 260px;min-width:200px;padding:.72rem .95rem;border-radius:11px;
  border:1px solid var(--line);background:var(--bg-soft);color:var(--text);font-size:.95rem;
}
input[type=search]:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:transparent}
input[type=search]::placeholder{color:var(--muted)}
.btn{
  padding:.72rem 1rem;border-radius:11px;border:1px solid var(--line);
  background:var(--bg-soft);color:var(--muted);font-size:.85rem;cursor:pointer;white-space:nowrap
}
.btn[aria-pressed=true]{background:var(--accent-soft);border-color:var(--accent);color:var(--text)}

/* Kartenraster */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:.75rem;padding-bottom:4rem}
.card{
  display:flex;align-items:baseline;gap:.6rem;padding:.85rem 1rem;
  background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
  color:var(--text);transition:background .15s,border-color .15s,transform .15s
}
.card:hover{background:var(--card-hover);border-color:var(--accent);transform:translateY(-1px);text-decoration:none}
.card .name{font-weight:600;font-size:.94rem;overflow-wrap:anywhere}
.card .n{margin-left:auto;color:var(--muted);font-size:.78rem;font-variant-numeric:tabular-nums;
  background:var(--bg-soft);border-radius:999px;padding:.1rem .5rem;flex:none}
.card[hidden]{display:none}

/* Linkliste – Feed-Layout: grosses Vorschaubild, Titel darunter */
ul.links{
  list-style:none;padding:0;margin:0 0 4rem;
  display:grid;grid-template-columns:repeat(auto-fill,minmax(292px,1fr));
  gap:1.6rem 1.15rem;align-items:start
}
ul.links li{background:none;border:0;border-radius:0;overflow:visible}
ul.links li[hidden]{display:none}
ul.links a{
  display:flex;flex-direction:column;gap:.6rem;padding:0;color:var(--text)
}
ul.links a:hover{text-decoration:none}

/* Bild gross und randlos, wie in einem Videofeed */
.thumb{
  display:block;position:relative;width:100%;aspect-ratio:16/9;
  border-radius:12px;overflow:hidden;background:#0a0c12
}
.thumb img{
  width:100%;height:100%;object-fit:cover;display:block;background:#0a0c12;
  transition:transform .3s ease,filter .2s ease
}
ul.links a:hover .thumb img{transform:scale(1.04);filter:brightness(1.1)}
.thumb.noimg img{display:none}
.thumb.noimg{background:linear-gradient(135deg,#141827,#0c0f18)}
.thumb.noimg::after{
  content:"🎬";position:absolute;inset:0;display:grid;place-items:center;
  font-size:1.6rem;opacity:.45
}
/* dezenter Play-Hinweis beim Ueberfahren */
.thumb::before{
  content:"";position:absolute;inset:0;z-index:1;opacity:0;
  background:radial-gradient(circle at 50% 50%,rgba(0,0,0,.42),rgba(0,0,0,.18));
  transition:opacity .2s ease
}
ul.links a:hover .thumb::before{opacity:1}
.thumb::after{pointer-events:none}

ul.links .tx{display:flex;flex-direction:column;gap:.18rem;min-width:0;padding:0 .1rem}
ul.links .t{
  font-weight:600;font-size:.95rem;line-height:1.34;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
  overflow:hidden;overflow-wrap:anywhere
}
ul.links .meta{
  color:var(--muted);font-size:.78rem;display:flex;align-items:center;
  gap:.4rem;min-width:0
}
ul.links .meta .host{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
ul.links .go{
  flex:none;color:var(--muted);font-size:.72rem;border:1px solid var(--line);
  border-radius:7px;padding:.02rem .38rem
}
ul.links a:hover .go{color:var(--accent);border-color:var(--accent)}
body.no-thumbs .thumb{display:none}
body.no-thumbs ul.links{gap:1rem .9rem}
body.no-thumbs ul.links a{
  background:var(--card);border:1px solid var(--line);border-radius:11px;
  padding:.7rem .85rem
}
body.no-thumbs ul.links a:hover{border-color:var(--accent);background:var(--card-hover)}
body.no-thumbs ul.links .t{-webkit-line-clamp:3}

.empty{color:var(--muted);padding:2rem 0 4rem}
.chips{display:flex;flex-wrap:wrap;gap:.35rem;margin:0 0 2rem}
.chip{
  font-size:.78rem;color:var(--muted);border:1px solid var(--line);border-radius:999px;
  padding:.2rem .6rem;background:var(--bg-soft)
}
.chip b{color:var(--text);font-weight:600}
.chip:hover{color:var(--accent);border-color:var(--accent);text-decoration:none}
section.grp{margin-bottom:2rem;scroll-margin-top:70px}
section.grp[hidden]{display:none}
section.grp h2{font-size:1.05rem;margin:0 0 .6rem;display:flex;align-items:center;gap:.55rem}
section.grp h2 .n{font-size:.75rem;color:var(--muted);background:var(--card);
  border:1px solid var(--line);border-radius:999px;padding:.05rem .45rem;font-weight:500}

footer{border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;padding:1.6rem 0 2.4rem}
footer p{margin:.25rem 0}

/* Altersabfrage */
.gate{
  position:fixed;inset:0;z-index:100;display:grid;place-items:center;padding:1.5rem;
  background:rgba(8,10,16,.94);backdrop-filter:blur(6px)
}
.gate[hidden]{display:none}
.gate .box{
  max-width:440px;background:var(--card);border:1px solid var(--line);
  border-radius:18px;padding:1.8rem;text-align:center
}
.gate h2{margin:0 0 .6rem;font-size:1.25rem}
.gate p{color:var(--muted);font-size:.9rem;margin:0 0 1.3rem}
.gate .big{
  background:var(--accent);color:#fff;border:0;border-radius:11px;
  padding:.8rem 1.4rem;font-size:.95rem;font-weight:650;cursor:pointer
}
.gate .leave{display:block;margin-top:1rem;font-size:.82rem;color:var(--muted)}

@media(max-width:900px){
  ul.links{grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1.4rem 1rem}
}
@media(max-width:620px){
  .controls{top:56px}
  .card .name{font-size:.9rem}
  ul.links{grid-template-columns:1fr;gap:1.5rem}
  ul.links .t{font-size:1rem}
}
"""

JS = """
(function () {
  // Altersabfrage – nur einmal pro Browser
  var gate = document.getElementById('gate');
  if (gate) {
    var KEY = 'videothek18';
    var ok = false;
    try { ok = localStorage.getItem(KEY) === '1'; } catch (e) {}
    gate.hidden = ok;
    var go = gate.querySelector('[data-confirm]');
    if (go) go.addEventListener('click', function () {
      try { localStorage.setItem(KEY, '1'); } catch (e) {}
      gate.hidden = true;
      var input = document.querySelector('[data-search]');
      if (input) input.focus();
    });
  }

  // Thumbnails an/aus (Auswahl merken)
  var TK = 'videothekThumbs';
  var thumbBtn = document.querySelector('[data-thumbs]');
  var applyThumbs = function (on) {
    document.body.classList.toggle('no-thumbs', !on);
    if (thumbBtn) {
      thumbBtn.setAttribute('aria-pressed', String(on));
      thumbBtn.textContent = on ? 'Thumbnails: an' : 'Thumbnails: aus';
    }
  };
  var thumbsOn = true;
  try { thumbsOn = localStorage.getItem(TK) !== '0'; } catch (e) {}
  applyThumbs(thumbsOn);
  if (thumbBtn) {
    thumbBtn.addEventListener('click', function () {
      thumbsOn = !thumbsOn;
      try { localStorage.setItem(TK, thumbsOn ? '1' : '0'); } catch (e) {}
      applyThumbs(thumbsOn);
    });
  }
  // Fehlgeschlagene Bilder -> Platzhalter statt kaputtem Icon
  document.addEventListener('error', function (e) {
    var img = e.target;
    if (img && img.tagName === 'IMG' && img.parentElement &&
        img.parentElement.classList.contains('thumb')) {
      img.parentElement.classList.add('noimg');
    }
  }, true);

  // Suche
  var input = document.querySelector('[data-search]');
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-term]'));
  var empty = document.querySelector('[data-empty]');
  if (input && items.length) {
    var filter = function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      items.forEach(function (el) {
        var hit = !q || el.getAttribute('data-term').indexOf(q) !== -1;
        el.hidden = !hit;
        if (hit) shown++;
      });
      if (empty) empty.hidden = shown !== 0;
    };
    input.addEventListener('input', filter);
    input.addEventListener('search', filter);
    document.addEventListener('keydown', function (e) {
      if (e.key === '/' && document.activeElement !== input) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    });
  }

  // Ein-Datei-Variante: Gruppen ausblenden, wenn nichts passt
  var groups = Array.prototype.slice.call(document.querySelectorAll('section.grp'));
  if (input && groups.length) {
    input.addEventListener('input', function () {
      var q = input.value.trim().toLowerCase();
      groups.forEach(function (g) {
        var nameHit = !q || g.getAttribute('data-term').indexOf(q) !== -1;
        var hits = 0;
        Array.prototype.slice.call(g.querySelectorAll('li[data-term]')).forEach(function (li) {
          var hit = nameHit || li.getAttribute('data-term').indexOf(q) !== -1;
          li.hidden = !hit;
          if (hit) hits++;
        });
        g.hidden = !nameHit && hits === 0;
      });
    });
  }

  // Sortierung (nur Startseite): A–Z oder meiste Links
  var grid = document.querySelector('[data-grid]');
  var sortBtn = document.querySelector('[data-sort]');
  if (grid && sortBtn) {
    var mode = 'az';
    var apply = function () {
      var cards = Array.prototype.slice.call(grid.children);
      cards.sort(function (a, b) {
        if (mode === 'count') {
          return Number(b.dataset.count) - Number(a.dataset.count) ||
                 a.dataset.name.localeCompare(b.dataset.name, 'de');
        }
        return a.dataset.name.localeCompare(b.dataset.name, 'de');
      });
      cards.forEach(function (c) { grid.appendChild(c); });
      sortBtn.setAttribute('aria-pressed', mode === 'count');
      sortBtn.textContent = mode === 'count' ? 'Sortierung: meiste Links' : 'Sortierung: A–Z';
    };
    sortBtn.addEventListener('click', function () {
      mode = mode === 'az' ? 'count' : 'az';
      apply();
    });
  }
})();
"""

GATE = """
<div class="gate" id="gate" hidden>
  <div class="box">
    <h2>Inhalte nur für Erwachsene</h2>
    <p>Diese Seite enthält Links zu pornografischen Inhalten und richtet sich
       ausschließlich an Personen ab 18 Jahren.</p>
    <button class="big" type="button" data-confirm>Ich bin 18 oder älter</button>
    <a class="leave" href="https://www.google.com/">Seite verlassen</a>
  </div>
</div>
"""


def esc(text: str) -> str:
    return html.escape(text, quote=True)


# Versionskennung fuer CSS/JS: erzwingt nach jedem Build einen frischen Download,
# damit Browser nach Aenderungen nicht die alte Datei aus dem Cache zeigen.
ASSET_VERSIONS: dict[str, str] = {}


def asset_version(name: str) -> str:
    return ASSET_VERSIONS.get(name, "0")


def version_assets() -> None:
    """Hasht die ausgelieferten CSS/JS-Inhalte und merkt sich die Kennung."""
    for name in ("style.css", "app.js"):
        data = (CSS if name.endswith(".css") else JS).encode("utf-8")
        ASSET_VERSIONS[name] = hashlib.sha1(data).hexdigest()[:8]


def page(title: str, body: str, root: str, description: str = SITE_DESC) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<meta name="rating" content="adult">
<meta name="description" content="{esc(description)}">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{root}assets/style.css?v={asset_version("style.css")}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>">
</head>
<body>
{GATE}
{body}
<script src="{root}assets/app.js?v={asset_version("app.js")}" defer></script>
</body>
</html>
"""


def footer(total: int) -> str:
    return f"""<footer>
  <div class="wrap">
    <p>{esc(SITE_TITLE)} – {total} Links, sortiert nach Darstellerin.</p>
    <p>Alle Links führen zu externen Websites. Für deren Inhalte sind die
       jeweiligen Anbieter verantwortlich. Keine Inhalte werden hier gehostet.</p>
  </div>
</footer>
"""


def build_index(entries, total: int) -> str:
    rows = sorted(entries.values(), key=lambda e: e["name"].casefold())
    cards = []
    for entry in rows:
        name = entry["name"]
        slug = eo.slugify(name)
        count = len(entry["links"])
        cards.append(
            f'<a class="card" href="p/{slug}/index.html" '
            f'data-name="{esc(name)}" data-term="{esc(name.casefold())}" data-count="{count}">'
            f'<span class="name">{esc(name)}</span>'
            f'<span class="n">{count}</span></a>'
        )

    body = f"""<header class="top">
  <div class="wrap">
    <a class="brand" href="./">Video<span>thek</span></a>
    <span class="count">{len(rows)} Darstellerinnen · {total} Links</span>
  </div>
</header>
<main class="wrap">
  <section class="hero">
    <h1>Videothek</h1>
    <p>{esc(SITE_DESC)} Wähle eine Darstellerin – jede Seite listet alle
       gespeicherten Links, durchsuchbar und direkt anklickbar.</p>
    <div class="stats">
      <span class="pill"><b>{len(rows)}</b> Ordner</span>
      <span class="pill"><b>{total}</b> Links</span>
      <span class="pill">Tipp: <b>/</b> springt in die Suche</span>
    </div>
  </section>

  <div class="controls">
    <input type="search" data-search placeholder="Nach Darstellerin suchen …" aria-label="Nach Darstellerin suchen">
    <button class="btn" type="button" data-sort aria-pressed="false">Sortierung: A–Z</button>
  </div>

  <div class="grid" data-grid>
    {"".join(cards)}
  </div>
  <p class="empty" data-empty hidden>Keine Treffer.</p>
</main>
{footer(total)}"""
    return page(f"{SITE_TITLE} – Links nach Darstellerin", body, "", SITE_DESC)


def load_thumbs() -> dict[str, str]:
    """Liest die von tools/thumbnails.py ermittelten Vorschaubild-URLs."""
    path = ROOT / "data" / "thumbs.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        k: v
        for k, v in data.items()
        if isinstance(v, str) and v.startswith(("http://", "https://", "/"))
    }


def host_of(url: str) -> str:
    match = re.match(r"https?://([^/]+)/?", url)
    return (match.group(1) if match else "").removeprefix("www.")


def link_item(title: str, url: str, thumbs: dict[str, str]) -> str:
    """Ein Listeneintrag mit Vorschaubild (falls bekannt) und Titel."""
    thumb = thumbs.get(url)
    if thumb:
        img = (
            f'<img src="{esc(thumb)}" alt="" loading="lazy" decoding="async" '
            f'referrerpolicy="no-referrer" width="480" height="270">'
        )
        thumb_html = f'<span class="thumb">{img}</span>'
    else:
        thumb_html = '<span class="thumb noimg"></span>'
    return (
        f'<li data-term="{esc((title + " " + url).casefold())}">'
        f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer nofollow">'
        f"{thumb_html}"
        f'<span class="tx"><span class="t">{esc(title)}</span>'
        f'<span class="meta"><span class="host">{esc(host_of(url))}</span>'
        f'<span class="go">ansehen ↗</span></span></span></a></li>'
    )


def build_person(entry, thumbs: dict[str, str] | None = None) -> str:
    name = entry["name"]
    items = sorted(
        ((title, url) for url, title in entry["links"].items()),
        key=lambda t: (eo.normalize(t[0]), t[1]),
    )
    thumbs = thumbs or {}
    with_thumb = sum(1 for _, url in items if url in thumbs)
    lis = [link_item(title, url, thumbs) for title, url in items]

    body = f"""<header class="top">
  <div class="wrap">
    <a class="brand" href="../../index.html">Video<span>thek</span></a>
    <a class="back" href="../../index.html">← Alle Darstellerinnen</a>
  </div>
</header>
<main class="wrap">
  <section class="hero">
    <h1>{esc(name)}</h1>
    <div class="stats">
      <span class="pill"><b>{len(items)}</b> Links</span>
      <span class="pill"><b>{with_thumb}</b> mit Vorschaubild</span>
    </div>
  </section>

  <div class="controls">
    <input type="search" data-search placeholder="Titel durchsuchen …" aria-label="Titel durchsuchen">
    <button class="btn" type="button" data-thumbs aria-pressed="true">Thumbnails: an</button>
  </div>

  <ul class="links">
    {"".join(lis)}
  </ul>
  <p class="empty" data-empty hidden>Keine Treffer.</p>
</main>
{footer(len(items))}"""
    return page(f"{name} – {SITE_TITLE}", body, "../../")


def build_standalone(entries, total: int, thumbs: dict[str, str] | None = None) -> str:
    """Alles in einer einzigen HTML-Datei – laeuft auch ohne Webserver."""
    thumbs = thumbs or {}
    rows = sorted(entries.values(), key=lambda e: e["name"].casefold())
    sections = []
    nav = []
    for entry in rows:
        name = entry["name"]
        anchor = eo.slugify(name)
        count = len(entry["links"])
        nav.append(f'<a class="chip" href="#{anchor}">{esc(name)} <b>{count}</b></a>')
        items = sorted(
            ((title, url) for url, title in entry["links"].items()),
            key=lambda t: (eo.normalize(t[0]), t[1]),
        )
        lis = "".join(link_item(title, url, thumbs) for title, url in items)
        sections.append(
            f'<section class="grp" id="{anchor}" data-term="{esc(name.casefold())}">'
            f'<h2>{esc(name)} <span class="n">{count}</span></h2>'
            f'<ul class="links">{lis}</ul></section>'
        )

    body = f"""<header class="top">
  <div class="wrap">
    <span class="brand">Video<span>thek</span></span>
    <span class="count">{len(rows)} Darstellerinnen · {total} Links</span>
  </div>
</header>
<main class="wrap">
  <section class="hero">
    <h1>Videothek</h1>
    <p>Alles in einer Datei – {len(rows)} Darstellerinnen, {total} Links.
       Die Suche filtert Darstellerinnen und Titel gleichzeitig.</p>
  </section>
  <div class="controls">
    <input type="search" data-search placeholder="Darstellerin oder Titel suchen …" aria-label="Suchen">
    <button class="btn" type="button" data-thumbs aria-pressed="true">Thumbnails: an</button>
  </div>
  <div class="chips">{''.join(nav)}</div>
  {''.join(sections)}
  <p class="empty" data-empty hidden>Keine Treffer.</p>
</main>
{footer(total)}"""
    return page(f"{SITE_TITLE} – alle Links", body, "")


def main() -> int:
    sources = eo.source_files()
    if not sources:
        print("Keine Quelldateien gefunden.", file=sys.stderr)
        return 1

    entries = eo.parse(sources)
    thumbs = load_thumbs()
    total_unique = len({u for e in entries.values() for u in e["links"]})
    total = sum(len(e["links"]) for e in entries.values())

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "p").mkdir()

    if not thumbs:
        print(
            "Hinweis: data/thumbs.json ist leer – Seiten werden ohne "
            "Vorschaubilder gebaut (Platzhalter). Fuellen mit: "
            "python3 tools/thumbnails.py",
            file=sys.stderr,
        )

    version_assets()

    (OUT / "assets" / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (OUT / "assets" / "app.js").write_text(JS.strip() + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "robots.txt").write_text(
        "User-agent: *\nDisallow: /\n", encoding="utf-8"
    )
    (OUT / "index.html").write_text(build_index(entries, total), encoding="utf-8")

    for entry in entries.values():
        folder = OUT / "p" / eo.slugify(entry["name"])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "index.html").write_text(
            build_person(entry, thumbs), encoding="utf-8"
        )

    (OUT / "videothek.html").write_text(
        build_standalone(entries, total, thumbs), encoding="utf-8"
    )

    print(
        f"{len(entries)} Darstellerinnen-Seiten erzeugt "
        f"({total} Zuordnungen, {total_unique} eindeutige Links, "
        f"{len(thumbs)} Vorschaubilder) -> {OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
