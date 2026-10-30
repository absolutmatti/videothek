#!/usr/bin/env python3
"""Erzeugt aus ``Lesezeichen.md`` pro Darstellerin einen Ordner mit ihren Links.

Ablauf
------
1. Die Quelldatei wird zeilenweise gelesen. Jede Zeile kann
   - eine Ueberschrift (Darstellerinnenname, z. B. ``Anissa Kate``),
   - ein Link ``[Titel](URL)`` (auch mehrere pro Zeile) oder
   - Rauschen (``about:blank``, ``Neuer Tab``, ``---``, ``[Ordnername]``)
   sein.
2. Jede Darstellerin bekommt einen Ordner mit:
   - ``README.md``  – Titel + klickbare Linkliste (alphabetisch, ohne Doppel)
   - ``links.md``   – nur die nackten URLs, eine pro Zeile (gut zum Importieren)
3. Zusaetzlich entstehen ``README.md`` (Gesamtuebersicht) im Projektwurzel-
   verzeichnis sowie ``_Ursprungsdaten/Lesezeichen.md`` (unveraenderte Kopie).

Aufruf:
    python3 tools/erstelle_ordner.py [Quelldatei]

Standard-Quelldatei ist ``_Ursprungsdaten/Lesezeichen.md``.
"""

from __future__ import annotations

import re
import shutil
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "_Ursprungsdaten" / "Lesezeichen.md"
# Merkt sich, welche Ordner zuletzt erzeugt wurden (fuer saubere Neu-Generierung)
STATE_FILE = ROOT / "tools" / ".ordnerliste"

LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
# " - Porn00" bzw. " – Porn00" am Titelende entfernen
SITE_SUFFIX_RE = re.compile(r"\s*[-\u2013\u2014|]\s*Porn00\s*$", re.IGNORECASE)
# Trenner zwischen Darstellerinnen und Filmtitel
CAST_TITLE_SPLIT_RE = re.compile(r"\s+[-\u2013\u2014|]\s+")
CAST_SPLIT_RE = re.compile(r"\s*(?:&|,|\bund\b|\band\b)\s*")

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
}


def normalize(text: str) -> str:
    """Kleinschreibung ohne Sonderzeichen/Leerzeichen – fuer Vergleiche."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_person_name(name: str) -> bool:
    """Grobe Plausibilitaetspruefung: 1–3 Woerter, jedes gross geschrieben."""
    words = name.split()
    if not 1 <= len(words) <= 3:
        return False
    if any(w.lower().strip(".,!?") in NOT_A_NAME for w in words):
        return False
    return all(w[:1].isupper() for w in words)


def split_cast(title: str) -> tuple[list[str], str]:
    """Zerlegt einen Linktitel in (Darstellerinnen, Filmtitel)."""
    title = SITE_SUFFIX_RE.sub("", title.strip()).strip()
    parts = CAST_TITLE_SPLIT_RE.split(title, maxsplit=1)
    if len(parts) == 2:
        cast_raw, movie = parts
        names = [n.strip(" .") for n in CAST_SPLIT_RE.split(cast_raw)]
        names = [n for n in names if n and is_person_name(n)]
        if names:
            return names, movie.strip(" -\u2013\u2014")
    return [], title


def parse(source: Path):
    """Liest die Lesezeichen und liefert (Reihenfolge der Namen, Links)."""
    entries: "OrderedDict[str, dict[str, str]]" = OrderedDict()
    section: str | None = None

    def canonical(name: str) -> tuple[str, str]:
        """Liefert (Schluessel, Anzeigename) – Alias-Schreibweisen werden aufgeloest."""
        display = NAME_ALIASES.get(normalize(name), name)
        return normalize(display), display

    def register(name: str) -> tuple[str, str]:
        key, display = canonical(name)
        entries.setdefault(key, {"name": display, "links": {}})
        return key, display

    def add(name: str, title: str, url: str) -> None:
        key, _ = register(name)
        entries[key]["links"].setdefault(url, title)

    for raw_line in source.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        found = LINK_RE.findall(line)
        rest = LINK_RE.sub("", line).strip()

        if rest.lower() in NOISE:
            rest = ""

        if rest:
            name = rest.replace("\u221a", "").strip()
            if is_person_name(name):
                section = register(name)[1]

        for title, url in found:
            names, movie = split_cast(title)
            if not names and section:
                names = [section]
            for name in names:
                add(name, movie or title, url)

    return entries


def md_escape(text: str) -> str:
    return text.replace("[", r"\[").replace("]", r"\]")


def write_folder(folder: Path, name: str, links: dict[str, str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)

    items = sorted(
        ((title, url) for url, title in links.items()),
        key=lambda t: (normalize(t[0]), t[1]),
    )

    readme = [
        f"# {name}",
        "",
        f"**{len(items)} Links**",
        "",
        "## Links",
        "",
    ]
    for title, url in items:
        readme.append(f"- [{md_escape(title) or url}]({url})")
    readme.append("")
    (folder / "README.md").write_text("\n".join(readme), encoding="utf-8")

    (folder / "links.md").write_text(
        "\n".join(url for _, url in items) + "\n", encoding="utf-8"
    )


def write_root_readme(entries) -> None:
    rows = sorted(
        entries.values(), key=lambda e: (normalize(e["name"]), e["name"])
    )
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
        lines.append(f"| [{md_escape(name)}]({folder}/README.md) | {len(entry['links'])} |")
    lines += [
        "",
        "## Hinweise",
        "",
        "- Jeder Ordner enthaelt `README.md` (klickbare Liste) und "
        "`links.md` (nur URLs, eine pro Zeile).",
        "- Eintraege, in denen mehrere Darstellerinnen vorkommen "
        "(`Name & Name - Titel`), liegen in **jedem** betroffenen Ordner.",
        "- Die 40 Darstellerinnen mit eigener Ueberschrift in der Quelldatei "
        "haben viele Links; die uebrigen Ordner enthalten oft nur 1–2 Titel, "
        "in denen die Darstellerin als Co-Star auftaucht.",
        "- Die Originaldatei liegt unveraendert in "
        "`_Ursprungsdaten/Lesezeichen.md`.",
        "- Alles neu erzeugen: `python3 tools/erstelle_ordner.py`",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    source = Path(argv[1]).expanduser() if len(argv) > 1 else DEFAULT_SOURCE
    if not source.is_file():
        print(f"Quelldatei nicht gefunden: {source}", file=sys.stderr)
        return 1

    backup = DEFAULT_SOURCE
    backup.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != backup.resolve():
        shutil.copyfile(source, backup)

    entries = parse(source)

    # Alte, von diesem Skript erzeugte Darstellerinnen-Ordner entfernen,
    # damit z. B. Tippfehler im Namen nicht als Leiche liegen bleiben.
    names = [e["name"] for e in entries.values()]
    duplicates = [n for n, c in Counter(names).items() if c > 1]
    if duplicates:
        print(f"Fehler: doppelte Ordnernamen: {duplicates}", file=sys.stderr)
        return 1
    known = {e["name"].replace("/", "-") for e in entries.values()}
    if (STATE_FILE).is_file():
        for old in (STATE_FILE).read_text(encoding="utf-8").splitlines():
            old = old.strip()
            if old and old not in known and (ROOT / old).is_dir():
                shutil.rmtree(ROOT / old)

    for entry in entries.values():
        write_folder(ROOT / entry["name"].replace("/", "-"), entry["name"], entry["links"])

    (STATE_FILE).write_text(
        "\n".join(sorted(known)) + "\n", encoding="utf-8"
    )
    write_root_readme(entries)

    for entry in sorted(entries.values(), key=lambda e: normalize(e["name"])):
        print(f"{len(entry['links']):4d}  {entry['name']}")
    print(f"\n{len(entries)} Ordner erzeugt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
