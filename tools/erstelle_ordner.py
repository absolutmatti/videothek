#!/usr/bin/env python3
"""Erzeugt aus den Lesezeichen-Dateien pro Darstellerin einen Ordner mit Links.

Unterstuetzte Quellformate (beide duerfen gemischt vorkommen, auch mehrere
Links pro Zeile):

* Markdown:   ``[Titel](https://...)``
* Nur-URL:    ``https://...https://...``  (aneinandergeklebt, ohne Trenner)
* Ueberschriften: eine eigene Zeile mit dem Namen, optional mit Doppelpunkt
  (``Anissa Kate`` oder ``Brianna Bourbon:``). Folgende Links ohne eigenen
  Namen landen in diesem Abschnitt.

Nicht uebernommen werden Darstellerinnen-Profilseiten der Form
``https://www.<website>.com/star-name/<name>/``.

Ergebnis pro Darstellerin:
  <Name>/README.md   klickbare, alphabetisch sortierte Linkliste
  <Name>/links.md    nur die URLs, eine pro Zeile

Aufruf:
    python3 tools/erstelle_ordner.py                 # alle Dateien in _Ursprungsdaten/
    python3 tools/erstelle_ordner.py neue-links.md   # weitere Datei ergaenzen
"""

from __future__ import annotations

import re
import shutil
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "_Ursprungsdaten"
# Merkt sich, welche Ordner zuletzt erzeugt wurden (fuer saubere Neu-Generierung)
STATE_FILE = ROOT / "tools" / ".ordnerliste"

LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
URL_RE = re.compile(r"https?://[^\s\]\)<>\"']+")
# " - Porn00" bzw. " – Porn00" am Titelende entfernen
SITE_SUFFIX_RE = re.compile(r"\s*[-\u2013\u2014|]\s*Porn00\s*$", re.IGNORECASE)
# Trenner zwischen Darstellerinnen und Filmtitel
CAST_TITLE_SPLIT_RE = re.compile(r"\s+[-\u2013\u2014|]\s+")
CAST_SPLIT_RE = re.compile(r"\s*(?:&|,|\bund\b|\band\b)\s*")
# Darstellerinnen-Profilseiten: .../star-name/<name>/
PROFILE_RE = re.compile(r"^https?://[^/]+/star-name/", re.IGNORECASE)
# Kennungen, die an Slugs angehaengt werden (z. B. "-5lhbwm", "-xwfg8"):
# 5–8 Zeichen, enthalten eine Ziffer oder hoechstens einen Vokal.
ID_SUFFIX_RE = re.compile(r"(-[a-z0-9]{3,8})+$", re.IGNORECASE)
# Schreibweisen, die in Slugs klein geschrieben sind
WORD_FIX = {
    "bbc": "BBC", "bbcs": "BBC", "milf": "MILF", "milfs": "MILFs", "pov": "POV",
    "dp": "DP", "gb": "GB", "xxx": "XXX", "bbw": "BBW", "bdsm": "BDSM",
    "ts": "TS", "hd": "HD", "creampie": "Creampie",
}
APOSTROPHE_RE = re.compile(r"\s+(s|t|d|ll|re|ve|m)\b(?=\s|$)")

NOISE = {"---", "about:blank", "neuer tab", "[ordnername]", "ordnername"}
# Woerter, die nie Teil eines Namens sind (Schutz gegen Fehl-Treffer)
NOT_A_NAME = {"porn00", "porn", "videos", "hd", "incorporated", "inc"}

# Schreibweisen zusammenfuehren: Schluessel = normalisiert, Wert = Anzeigename.
# Die Schreibweise des Ziels gewinnt, damit keine doppelten Ordner entstehen.
NAME_ALIASES = {
    "jordanmax": "Jordan Maxx",
    "xxlaynamari": "Xxlayna Marie",
    "mckenzielee": "McKenzie Lee",
    "trinitystclair": "Trinity St Clair",
    "lillyhall": "Lilly Hall",
}


def normalize(text: str) -> str:
    """Kleinschreibung ohne Sonderzeichen/Leerzeichen – fuer Vergleiche."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def is_person_name(name: str) -> bool:
    """Grobe Plausibilitaetspruefung: 1–3 Woerter, jedes gross geschrieben."""
    words = name.split()
    if not 1 <= len(words) <= 3:
        return False
    if any(w.lower().strip(".,!?") in NOT_A_NAME for w in words):
        return False
    return all(w[:1].isupper() for w in words)


def split_cast(title: str) -> tuple[list[str], str]:
    """Zerlegt einen Markdown-Linktitel in (Darstellerinnen, Filmtitel)."""
    title = SITE_SUFFIX_RE.sub("", title.strip()).strip()
    parts = CAST_TITLE_SPLIT_RE.split(title, maxsplit=1)
    if len(parts) == 2:
        cast_raw, movie = parts
        names = [n.strip(" .") for n in CAST_SPLIT_RE.split(cast_raw)]
        names = [n for n in names if n and is_person_name(n)]
        if names:
            return names, movie.strip(" -\u2013\u2014")
    return [], title


def title_from_url(url: str, person: str | None) -> str:
    """Baut aus einem Video-Slug einen lesbaren Titel."""
    path = url.split("?")[0].rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    if person:
        prefix = slugify(person)
        if slug.startswith(prefix + "-"):
            slug = slug[len(prefix) + 1:]
    while True:
        candidate = ID_SUFFIX_RE.search(slug)
        if not candidate:
            break
        token = candidate.group(0)[1:]
        vowels = sum(c in "aeiou" for c in token)
        has_digit = any(c.isdigit() for c in token)
        looks_like_id = vowels <= 1 and (has_digit or len(token) >= 5)
        if not looks_like_id:
            break
        slug = slug[: candidate.start()]
    if not slug:
        return url
    text = slug.replace("-", " ").strip()
    text = APOSTROPHE_RE.sub(r"'\1", text)
    return " ".join(
        WORD_FIX.get(w.lower(), w[:1].upper() + w[1:]) for w in text.split()
    )


def parse_file(path: Path, entries: "OrderedDict[str, dict]") -> None:
    section: str | None = None

    def register(name: str) -> str:
        display = NAME_ALIASES.get(normalize(name), name)
        key = normalize(display)
        entries.setdefault(key, {"name": display, "links": {}})
        return key

    def add(name: str | None, title: str, url: str) -> None:
        url = url.strip().strip("<>()[]").rstrip('.,;"\'')
        if not url.startswith("http") or PROFILE_RE.match(url):
            return
        name = name or section
        if not name:
            return
        key = register(name)
        entries[key]["links"].setdefault(url, title.strip() or url)

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 1) Markdown-Links [Titel](URL)
        for title, url in LINK_RE.findall(line):
            names, movie = split_cast(title)
            if names:
                for name in names:
                    add(name, movie or title, url)
            else:
                add(section, movie or title, url)

        rest = LINK_RE.sub("", line).strip()

        # 2) nackte, ggf. aneinandergeklebte URLs
        for chunk in re.split(r"(?=https?://)", rest):
            chunk = chunk.strip()
            if not chunk.startswith("http"):
                continue
            url = chunk.split()[0] if chunk.split() else chunk
            add(section, title_from_url(url, section), url)

        # 3) Text vor der ersten URL: Name / Ueberschrift?
        label = re.split(r"https?://", rest)[0].strip()
        label = label.rstrip(":").strip()
        if not label or label.lower() in NOISE:
            continue
        label = label.replace("\u221a", "").strip()
        if is_person_name(label):
            register(label)
            section = label


def parse(sources: list[Path]) -> "OrderedDict[str, dict]":
    entries: "OrderedDict[str, dict]" = OrderedDict()
    for path in sources:
        parse_file(path, entries)
    return entries


def md_escape(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def write_folder(folder: Path, name: str, links: dict[str, str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    items = sorted(
        ((title, url) for url, title in links.items()),
        key=lambda t: (normalize(t[0]), t[1]),
    )

    readme = [f"# {name}", "", f"**{len(items)} Links**", "", "## Links", ""]
    for title, url in items:
        readme.append(f"- [{md_escape(title) or url}]({url})")
    readme.append("")
    (folder / "README.md").write_text("\n".join(readme), encoding="utf-8")

    (folder / "links.md").write_text(
        "\n".join(url for _, url in items) + "\n", encoding="utf-8"
    )


def write_root_readme(entries) -> None:
    rows = sorted(entries.values(), key=lambda e: (normalize(e["name"]), e["name"]))
    total = sum(len(e["links"]) for e in rows)

    lines = [
        "# Videothek",
        "",
        f"{len(rows)} Darstellerinnen-Ordner mit insgesamt "
        f"{total} Links (ohne Doppelzaehlungen innerhalb eines Ordners).",
        "",
        "| Darstellerin | Links |",
        "| --- | ---: |",
    ]
    for entry in rows:
        name = entry["name"]
        folder = name.replace("/", "-").replace(" ", "%20")
        lines.append(
            f"| [{md_escape(name)}]({folder}/README.md) | {len(entry['links'])} |"
        )
    lines += [
        "",
        "## Hinweise",
        "",
        "- Jeder Ordner enthaelt `README.md` (klickbare Liste) und "
        "`links.md` (nur URLs, eine pro Zeile).",
        "- Eintraege mit mehreren Darstellerinnen (`Name & Name - Titel`) "
        "liegen in **jedem** betroffenen Ordner.",
        "- Darstellerinnen-Profilseiten (`.../star-name/<name>/`) werden "
        "bewusst nicht aufgenommen.",
        "- Die 40 Darstellerinnen mit eigener Ueberschrift in der ersten "
        "Quelldatei haben viele Links; die uebrigen Ordner enthalten oft nur "
        "1–2 Titel, in denen die Darstellerin als Co-Star auftaucht.",
        "- Quelldateien liegen unveraendert in `_Ursprungsdaten/`.",
        "- Alles neu erzeugen: `python3 tools/erstelle_ordner.py`",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    extra = [Path(a).expanduser() for a in argv[1:]]
    for path in extra:
        if not path.is_file():
            print(f"Quelldatei nicht gefunden: {path}", file=sys.stderr)
            return 1
        if path.resolve().parent != SOURCE_DIR.resolve():
            target = SOURCE_DIR / path.name
            if path.resolve() != target.resolve():
                shutil.copyfile(path, target)

    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        print(f"Keine Quelldateien in {SOURCE_DIR}", file=sys.stderr)
        return 1

    entries = parse(sources)

    names = [e["name"] for e in entries.values()]
    duplicates = [n for n, c in Counter(names).items() if c > 1]
    if duplicates:
        print(f"Fehler: doppelte Ordnernamen: {duplicates}", file=sys.stderr)
        return 1
    known = {e["name"].replace("/", "-") for e in entries.values()}

    # Alte, von diesem Skript erzeugte Ordner entfernen, damit z. B. Tippfehler
    # im Namen nicht als Leiche liegen bleiben.
    if STATE_FILE.is_file():
        for old in STATE_FILE.read_text(encoding="utf-8").splitlines():
            old = old.strip()
            if old and old not in known and (ROOT / old).is_dir():
                shutil.rmtree(ROOT / old)

    for entry in entries.values():
        write_folder(
            ROOT / entry["name"].replace("/", "-"), entry["name"], entry["links"]
        )

    STATE_FILE.write_text("\n".join(sorted(known)) + "\n", encoding="utf-8")
    write_root_readme(entries)

    print(f"Quellen: {', '.join(p.name for p in sources)}")
    for entry in sorted(entries.values(), key=lambda e: normalize(e["name"])):
        print(f"{len(entry['links']):4d}  {entry['name']}")
    print(f"\n{len(entries)} Ordner erzeugt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
