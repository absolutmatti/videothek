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

Die Inhalte kommen aus derselben Quelle wie die Ordner
(``tools/erstelle_ordner.py``), damit Website und Ordner nie auseinanderlaufen.

Aufruf:
    python3 tools/build_site.py
"""

from __future__ import annotations

import html
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

/* Linkliste */
ul.links{list-style:none;padding:0;margin:0 0 4rem;display:flex;flex-direction:column;gap:.45rem}
ul.links li{
  background:var(--card);border:1px solid var(--line);border-radius:11px;overflow:hidden
}
ul.links li:hover{border-color:var(--accent);background:var(--card-hover)}
ul.links a{
  display:flex;align-items:center;gap:.8rem;padding:.68rem .95rem;
  color:var(--text);font-size:.93rem
}
ul.links a:hover{text-decoration:none}
ul.links .t{overflow-wrap:anywhere}
ul.links .go{
  margin-left:auto;flex:none;color:var(--muted);font-size:.8rem;
  border:1px solid var(--line);border-radius:8px;padding:.05rem .45rem
}
ul.links li:hover .go{color:var(--accent);border-color:var(--accent)}
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

@media(max-width:560px){
  .controls{top:56px}
  .card .name{font-size:.9rem}
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
<link rel="stylesheet" href="{root}assets/style.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎬</text></svg>">
</head>
<body>
{GATE}
{body}
<script src="{root}assets/app.js" defer></script>
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


def build_person(entry) -> str:
    name = entry["name"]
    items = sorted(
        ((title, url) for url, title in entry["links"].items()),
        key=lambda t: (eo.normalize(t[0]), t[1]),
    )
    lis = []
    for title, url in items:
        lis.append(
            f'<li data-term="{esc((title + " " + url).casefold())}">'
            f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer nofollow">'
            f'<span class="t">{esc(title)}</span>'
            f'<span class="go">öffnen</span></a></li>'
        )

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
    </div>
  </section>

  <div class="controls">
    <input type="search" data-search placeholder="Titel durchsuchen …" aria-label="Titel durchsuchen">
  </div>

  <ul class="links">
    {"".join(lis)}
  </ul>
  <p class="empty" data-empty hidden>Keine Treffer.</p>
</main>
{footer(len(items))}"""
    return page(f"{name} – {SITE_TITLE}", body, "../../")


def build_standalone(entries, total: int) -> str:
    """Alles in einer einzigen HTML-Datei – laeuft auch ohne Webserver."""
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
        lis = "".join(
            f'<li data-term="{esc((title + " " + url).casefold())}">'
            f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer nofollow">'
            f'<span class="t">{esc(title)}</span>'
            f'<span class="go">öffnen</span></a></li>'
            for title, url in items
        )
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
  </div>
  <div class="chips">{''.join(nav)}</div>
  {''.join(sections)}
  <p class="empty" data-empty hidden>Keine Treffer.</p>
</main>
{footer(total)}"""
    return page(f"{SITE_TITLE} – alle Links", body, "")


def main() -> int:
    sources = sorted(eo.SOURCE_DIR.glob("*.md"))
    if not sources:
        print(f"Keine Quelldateien in {eo.SOURCE_DIR}", file=sys.stderr)
        return 1

    entries = eo.parse(sources)
    total_unique = len({u for e in entries.values() for u in e["links"]})
    total = sum(len(e["links"]) for e in entries.values())

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    (OUT / "p").mkdir()

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
        (folder / "index.html").write_text(build_person(entry), encoding="utf-8")

    (OUT / "videothek.html").write_text(
        build_standalone(entries, total), encoding="utf-8"
    )

    print(
        f"{len(entries)} Darstellerinnen-Seiten erzeugt "
        f"({total} Zuordnungen, {total_unique} eindeutige Links) -> {OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
