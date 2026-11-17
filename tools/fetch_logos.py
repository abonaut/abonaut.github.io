"""Sucht Logos für die Anbieter im Katalog und die Marken in logos/brands.json und wählt das beste Bild aus.

Aufruf (auf einem Mac, braucht sips):
  python3 -I tools/fetch_logos.py <Arbeitsordner> [id ...]           Kandidaten laden und auswählen
  python3 -I tools/fetch_logos.py --apply <Arbeitsordner> [id ...]   Auswahl nach logos/src übernehmen

Quellen pro Marke: apple-touch-icon und Symbole aus dem HTML der Website, /apple-touch-icon.png und der
Favicon-Dienst von Google (liefert die echte Grösse, nichts hochgerechnet). Gewählt wird das grösste fast quadratische
Bild ab 96 Pixel, Symbole der Website vor Google. Ergebnis: <Arbeitsordner>/picked/<id>.<endung> und picked.json.

Vor --apply die Auswahl ansehen (contact.html im Arbeitsordner). --apply übernimmt nur Marken, die noch nicht in
logos/sources.json stehen, ausser mit --replace. Die Dateien sind fremde Daten: nie ausführen, nur als Bild öffnen.
"""
import concurrent.futures
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CATALOG = os.path.join(ROOT, "catalog", "v1.json")
BRANDS = os.path.join(ROOT, "logos", "brands.json")
SOURCES = os.path.join(ROOT, "logos", "sources.json")
SOURCE_DIR = os.path.join(ROOT, "logos", "src")
USER_AGENT = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
MAX_BYTES = 2_000_000
MIN_PIXELS = 96
# Apple erlaubt Dritten das Apple-Logo nicht. Diese Anbieter behalten das Monogramm.
SKIP = {"apple-tv", "apple-music", "icloud"}


class IconLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        rel = values.get("rel", "").lower()
        href = values.get("href", "")
        if href and not href.startswith("data:") and ("apple-touch-icon" in rel or rel in ("icon", "shortcut icon", "manifest")):
            self.links.append((rel, values.get("sizes", ""), href))


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "de-CH,de;q=0.9"})
    with urllib.request.urlopen(request, timeout=15) as response:
        try:
            data = response.read(MAX_BYTES + 1)
        except http.client.IncompleteRead as error:
            data = error.partial
        if len(data) > MAX_BYTES:
            raise ValueError("zu gross")
        return response.geturl(), response.headers.get_content_type(), data


def image_type(data):
    """Dateityp anhand der ersten Bytes. HTML-Seiten (Bot-Schutz, Fehlerseiten) fallen weg."""
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpg"
    if data.startswith(b"\x00\x00\x01\x00"):
        return "ico"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def targets():
    """Alle Marken: (id, Website). Katalog-Anbieter zuerst."""
    with open(CATALOG, encoding="utf-8") as file:
        providers = json.load(file)["providers"]
    with open(BRANDS, encoding="utf-8") as file:
        brands = json.load(file)["brands"]
    result = [(provider["id"], provider["url"]) for provider in providers
              if provider.get("url") and provider["id"] not in SKIP]
    result += [(brand["id"], f"https://{brand['domain']}/") for brand in brands]
    return result


def candidate_urls(site):
    parts = urllib.parse.urlsplit(site)
    host = parts.hostname or ""
    pages = [site, f"https://{host}/"]
    labels = host.split(".")
    if len(labels) >= 2:
        pages.append(f"https://www.{'.'.join(labels[-2:])}/")
    found = []
    for page in dict.fromkeys(pages):
        try:
            final_url, content_type, data = get(page)
        except Exception:  # noqa: BLE001
            continue
        if "html" not in content_type:
            continue
        parser = IconLinks()
        parser.feed(data.decode("utf-8", errors="replace"))
        root = urllib.parse.urljoin(final_url, "/")
        for rel, sizes, href in parser.links:
            if rel == "manifest":
                found += manifest_icons(urllib.parse.urljoin(final_url, href))
                continue
            found.append((2 if "apple-touch-icon" in rel else 1, urllib.parse.urljoin(final_url, href)))
        found.append((2, urllib.parse.urljoin(root, "apple-touch-icon.png")))
        if parser.links:
            break
    main_host = ".".join(host.split(".")[-2:]) if host.count(".") >= 1 else host
    found.append((1, f"https://www.google.com/s2/favicons?domain={host}&sz=256"))
    if main_host != host:
        found.append((1, f"https://www.google.com/s2/favicons?domain={main_host}&sz=256"))
    unique = []
    for priority, url in found:
        if url not in [entry[1] for entry in unique]:
            unique.append((priority, url))
    return unique[:14]


def manifest_icons(url):
    """Symbole aus dem Web-App-Manifest, oft 192 oder 512 Pixel gross."""
    try:
        _, _, data = get(url)
        manifest = json.loads(data.decode("utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return []
    icons = []
    for icon in manifest.get("icons", []):
        source = icon.get("src")
        if source and "maskable" not in str(icon.get("purpose", "")):
            icons.append((2, urllib.parse.urljoin(url, source)))
    return icons


def dimensions(path):
    result = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path], capture_output=True, text=True)
    sizes = re.findall(r"pixel(?:Width|Height): (\d+)", result.stdout)
    return (int(sizes[0]), int(sizes[1])) if len(sizes) == 2 else (0, 0)


def fetch(identifier, site, work):
    folder = os.path.join(work, "candidates", identifier)
    shutil.rmtree(folder, ignore_errors=True)
    os.makedirs(folder)
    best = None
    for index, (priority, url) in enumerate(candidate_urls(site)):
        try:
            _, _, data = get(url)
        except Exception:  # noqa: BLE001
            continue
        extension = image_type(data)
        if extension is None:
            continue
        path = os.path.join(folder, f"{index}.{extension}")
        with open(path, "wb") as file:
            file.write(data)
        width, height = dimensions(path)
        side = min(width, height)
        if side < MIN_PIXELS or max(width, height) > side * 1.25:
            continue
        score = (min(side, 180), priority)
        if best is None or score > best[0]:
            best = (score, path, url, width)
    if best is None:
        return identifier, None
    _, path, url, width = best
    extension = os.path.splitext(path)[1]
    picked = os.path.join(work, "picked", identifier + extension)
    shutil.copyfile(path, picked)
    return identifier, {"file": picked, "source": url, "pixels": width}


def search(work, wanted):
    os.makedirs(os.path.join(work, "picked"), exist_ok=True)
    jobs = [(identifier, site) for identifier, site in targets() if not wanted or identifier in wanted]
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for identifier, result in pool.map(lambda job: fetch(job[0], job[1], work), jobs):
            results[identifier] = result
            print(f"{identifier}: {result['pixels']} px  {result['source']}" if result else f"{identifier}: nichts Brauchbares")
    path = os.path.join(work, "picked.json")
    previous = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as file:
            previous = json.load(file)
    previous.update({key: value for key, value in results.items() if value})
    with open(path, "w", encoding="utf-8") as file:
        json.dump(previous, file, indent=2, ensure_ascii=False)
    write_contact_sheet(work, previous)
    missing = sorted(key for key, value in results.items() if not value)
    print(f"\n{len(results) - len(missing)} gefunden, ohne: {', '.join(missing)}")


def write_contact_sheet(work, picked):
    tiles = "".join(
        f'<figure><div><img src="{os.path.relpath(entry["file"], work)}"></div><figcaption>{identifier}</figcaption></figure>'
        for identifier, entry in sorted(picked.items()))
    with open(os.path.join(work, "contact.html"), "w", encoding="utf-8") as file:
        file.write('<!doctype html><meta charset="utf-8"><style>body{background:#f2f2f7;margin:10px;display:flex;'
                   'flex-wrap:wrap;gap:8px;font:9px -apple-system}figure{margin:0;width:76px;text-align:center}'
                   'div{width:56px;height:56px;margin:auto;background:#fff;border-radius:14px;overflow:hidden;'
                   'box-shadow:0 0 0 1px #0002}img{width:56px;height:56px}</style>' + tiles)


def load_sources():
    with open(SOURCES, encoding="utf-8") as file:
        return json.load(file)


def save_sources(sources):
    """Eine Zeile pro Marke, wie von Hand geschrieben."""
    lines = []
    for key, value in sources.items():
        lines.append(f"  {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False, separators=(', ', ': '))}")
    text = "{\n" + ",\n".join(lines) + "\n}\n"
    json.loads(text)
    with open(SOURCES, "w", encoding="utf-8") as file:
        file.write(text)


def apply(work, wanted, replace):
    with open(os.path.join(work, "picked.json"), encoding="utf-8") as file:
        picked = json.load(file)
    sources = load_sources()
    added = []
    for identifier, entry in sorted(picked.items()):
        if wanted and identifier not in wanted:
            continue
        if identifier in sources and not replace:
            continue
        extension = os.path.splitext(entry["file"])[1]
        filename = identifier + extension
        shutil.copyfile(entry["file"], os.path.join(SOURCE_DIR, filename))
        sources[identifier] = {"file": filename, "source": entry["source"]}
        added.append(identifier)
    note = {key: value for key, value in sources.items() if key.startswith("_")}
    rest = {key: sources[key] for key in sorted(sources) if not key.startswith("_")}
    save_sources({**note, **rest})
    print(f"Übernommen: {len(added)} ({', '.join(added)})")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    replace = "--replace" in arguments
    arguments = [argument for argument in arguments if argument != "--replace"]
    if not arguments:
        sys.exit(__doc__)
    if arguments[0] == "--apply":
        if len(arguments) < 2:
            sys.exit(__doc__)
        apply(arguments[1], set(arguments[2:]), replace)
    else:
        search(arguments[0], set(arguments[1:]))
