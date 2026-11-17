#!/usr/bin/env python3
"""Baut das Logo-Paket logos/v1.json aus logos/src und trägt die Version im Katalog ein.

Aufruf (auf einem Mac, braucht das Programm sips): python3 -I tools/build_logos.py

Ablauf:
1. Für jeden Eintrag in logos/sources.json die Datei aus logos/src in PNG umwandeln, bei Bedarf mit weissem
   Rand quadratisch machen und auf höchstens 144 x 144 Pixel verkleinern.
2. Alle Logos als ein Paket schreiben: logos/v1.json mit {"schemaVersion": 1, "logos": [{"id", "name", "terms", "png"}]}.
   Die ID ist bei Katalog-Anbietern die Anbieter-ID, sonst die ID aus logos/brands.json. terms sind die Suchbegriffe
   (klein, ganze Wörter), mit denen die App ein Abo dem Logo zuordnet, auch ohne Katalogeintrag.
   Die App lädt immer das ganze Paket. So erfährt niemand, welche Abos jemand hat.
3. Im Katalog den Block "logos" mit Version (Prüfsumme des Pakets) und Pfad nachführen. Hat sich das Paket
   geändert, wird updatedAt auf heute gesetzt, damit die App den Katalog neu übernimmt.

Ein Logo entfernen (zum Beispiel auf Wunsch eines Anbieters): Eintrag in logos/sources.json löschen, Skript ausführen,
committen. Die App übernimmt das neue Paket ohne App-Update.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SOURCES = os.path.join(ROOT, "logos", "sources.json")
SOURCE_DIR = os.path.join(ROOT, "logos", "src")
BRANDS = os.path.join(ROOT, "logos", "brands.json")
PACKAGE = os.path.join(ROOT, "logos", "v1.json")
PACKAGE_PATH = "logos/v1.json"
CATALOG = os.path.join(ROOT, "catalog", "v1.json")
MAX_PIXELS = 144
MAX_BYTES = 80_000


def sips(*arguments):
    result = subprocess.run(["sips", *arguments], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def dimensions(path):
    output = sips("-g", "pixelWidth", "-g", "pixelHeight", path)
    width = int(re.search(r"pixelWidth: (\d+)", output).group(1))
    height = int(re.search(r"pixelHeight: (\d+)", output).group(1))
    return width, height


def prepare(source, padding, work_dir, identifier):
    target = os.path.join(work_dir, f"{identifier}.png")
    sips("-s", "format", "png", source, "--out", target)
    width, height = dimensions(target)
    side = max(width, height)
    padded = round(side * (1 + 2 * padding))
    if padded != width or padded != height:
        sips("-p", str(padded), str(padded), "--padColor", "FFFFFF", target, "--out", target)
    if padded > MAX_PIXELS:
        sips("-Z", str(MAX_PIXELS), target, "--out", target)
    with open(target, "rb") as file:
        data = file.read()
    if len(data) > MAX_BYTES:
        raise RuntimeError(f"{identifier}: {len(data)} Bytes, höchstens {MAX_BYTES}")
    return data


def update_catalog(version):
    with open(CATALOG, encoding="utf-8") as file:
        text = file.read()
    block = f'  "logos": {{\n    "version": "{version}",\n    "path": "{PACKAGE_PATH}"\n  }},\n'
    existing = re.search(r'  "logos": \{\n.*?\n  \},\n', text, flags=re.DOTALL)
    if existing:
        if existing.group(0) == block:
            return False
        text = text[:existing.start()] + block + text[existing.end():]
    else:
        marker = '  "groups": ['
        if marker not in text:
            raise RuntimeError("Im Katalog fehlt der Block groups")
        text = text.replace(marker, block + marker, 1)
    today = datetime.date.today().isoformat()
    text = re.sub(r'"updatedAt": "\d{4}-\d{2}-\d{2}"', f'"updatedAt": "{today}"', text, count=1)
    json.loads(text)  # Muss gültiges JSON bleiben.
    with open(CATALOG, "w", encoding="utf-8") as file:
        file.write(text)
    return True


def normalized_terms(terms):
    """Klein, ohne doppelte Einträge, Reihenfolge bleibt."""
    result = []
    for term in terms:
        term = term.strip().lower()
        if term and term not in result:
            result.append(term)
    return result


def main():
    with open(SOURCES, encoding="utf-8") as file:
        sources = {key: value for key, value in json.load(file).items() if not key.startswith("_")}
    with open(CATALOG, encoding="utf-8") as file:
        providers = {provider["id"]: provider for provider in json.load(file)["providers"]}
    with open(BRANDS, encoding="utf-8") as file:
        brands = {brand["id"]: brand for brand in json.load(file)["brands"]}

    duplicates = sorted(set(providers) & set(brands))
    if duplicates:
        sys.exit(f"In logos/brands.json und im Katalog zugleich: {', '.join(duplicates)}")
    unknown = sorted(set(sources) - set(providers) - set(brands))
    if unknown:
        sys.exit(f"Unbekannte IDs in logos/sources.json: {', '.join(unknown)}")

    entries = []
    with tempfile.TemporaryDirectory() as work_dir:
        for identifier in sorted(sources):
            entry = sources[identifier]
            source = os.path.join(SOURCE_DIR, entry["file"])
            if not os.path.isfile(source):
                sys.exit(f"{identifier}: Datei fehlt: logos/src/{entry['file']}")
            data = prepare(source, float(entry.get("padding", 0)), work_dir, identifier)
            if identifier in providers:
                provider = providers[identifier]
                name, terms = provider["name"], normalized_terms(provider["searchTerms"] + [provider["name"]])
            else:
                brand = brands[identifier]
                # Nur die Begriffe aus brands.json: Namen wie "Max" oder "Calm" wären als Suchbegriff zu allgemein.
                name, terms = brand["name"], normalized_terms(brand["terms"])
            entries.append({"id": identifier, "name": name, "terms": terms,
                            "png": base64.b64encode(data).decode("ascii")})

    # Eine Zeile pro Logo, damit Änderungen im Git-Verlauf lesbar bleiben.
    lines = ["    " + json.dumps(entry, ensure_ascii=False, separators=(", ", ": ")) for entry in entries]
    package = '{\n  "schemaVersion": 1,\n  "logos": [\n' + ",\n".join(lines) + "\n  ]\n}\n"
    json.loads(package)
    with open(PACKAGE, "w", encoding="utf-8") as file:
        file.write(package)

    version = hashlib.sha256(package.encode("utf-8")).hexdigest()[:12]
    changed = update_catalog(version)
    missing = sorted(set(providers) - set(sources))
    print(f"\n{len(entries)} Logos, {len(package) // 1024} KB, Version {version}"
          + (" (Katalog nachgeführt)" if changed else " (unverändert)"))
    print(f"Katalog-Anbieter ohne Logo (Monogramm): {', '.join(missing)}")


if __name__ == "__main__":
    main()
