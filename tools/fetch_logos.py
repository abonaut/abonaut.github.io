"""Lädt für jeden Anbieter im Katalog das offizielle App-Symbol (apple-touch-icon) von seiner Website.

Aufruf: python3 -I tools/fetch_logos.py <Zielordner> [anbieter-id ...]

Legt pro Anbieter die gefundenen Kandidaten in <Zielordner>/<id>/ ab und schreibt eine Übersicht nach
<Zielordner>/kandidaten.json. Ausgewählt und ins Paket übernommen wird erst von Hand (siehe logos/README.md):
die passende Datei nach logos/src/<id>.png kopieren, dann tools/build_logos.py ausführen.

Nur Standardbibliothek. Die Dateien sind fremde Daten: nie ausführen, nur als Bild öffnen.
"""
import http.client
import json
import os
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

CATALOG = os.path.join(os.path.dirname(__file__), "..", "catalog", "v1.json")
USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
MAX_BYTES = 2_000_000
# Apple erlaubt Dritten das Apple-Logo nicht. Diese Anbieter behalten das Monogramm.
SKIP = {"apple-tv", "apple-music", "icloud"}


class IconLinks(HTMLParser):
    """Sammelt <link rel="apple-touch-icon"> und <link rel="icon"> mit Grössenangabe."""

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        rel = values.get("rel", "").lower()
        href = values.get("href", "")
        if not href:
            return
        if "apple-touch-icon" in rel or rel in ("icon", "shortcut icon") or "mask-icon" in rel:
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
    if b"<svg" in data[:500]:
        return "svg"
    return None


def pages_for(url):
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    pages = [url, f"{parts.scheme}://{host}/"]
    labels = host.split(".")
    if len(labels) >= 2:
        main = ".".join(labels[-2:])
        pages.append(f"https://www.{main}/")
    unique = []
    for page in pages:
        if page not in unique:
            unique.append(page)
    return unique


def size_score(sizes):
    best = 0
    for item in sizes.lower().split():
        if "x" in item:
            try:
                best = max(best, int(item.split("x")[0]))
            except ValueError:
                pass
    return best


def candidates_for(provider_url):
    found = []
    for page in pages_for(provider_url):
        try:
            final_url, content_type, data = get(page)
        except Exception as error:  # noqa: BLE001
            print(f"    Seite {page}: {error}")
            continue
        if "html" not in content_type:
            continue
        parser = IconLinks()
        parser.feed(data.decode("utf-8", errors="replace"))
        if not parser.links:
            # Seite ohne Symbole (z. B. per JavaScript gebaut oder Bot-Schutz): nächste Seite versuchen.
            root = urllib.parse.urljoin(final_url, "/")
            found.append((1, 0, urllib.parse.urljoin(root, "favicon.ico")))
            continue
        for rel, sizes, href in parser.links:
            absolute = urllib.parse.urljoin(final_url, href)
            priority = 2 if "apple-touch-icon" in rel else (0 if "mask-icon" in rel else 1)
            found.append((priority, size_score(sizes), absolute))
        root = urllib.parse.urljoin(final_url, "/")
        found.append((2, 180, urllib.parse.urljoin(root, "apple-touch-icon.png")))
        found.append((2, 180, urllib.parse.urljoin(root, "apple-touch-icon-precomposed.png")))
        if found:
            break
    unique = []
    for item in sorted(found, key=lambda entry: (-entry[0], -entry[1])):
        if item[2] not in [entry[2] for entry in unique]:
            unique.append(item)
    return unique


def main(target, wanted):
    with open(CATALOG, encoding="utf-8") as file:
        providers = json.load(file)["providers"]
    os.makedirs(target, exist_ok=True)
    summary = {}
    for provider in providers:
        identifier = provider["id"]
        if wanted and identifier not in wanted:
            continue
        if identifier in SKIP or not provider.get("url"):
            print(f"{identifier}: übersprungen")
            continue
        print(f"{identifier}:")
        folder = os.path.join(target, identifier)
        os.makedirs(folder, exist_ok=True)
        saved = []
        for index, (priority, size, url) in enumerate(candidates_for(provider["url"])[:6]):
            try:
                _, content_type, data = get(url)
            except Exception as error:  # noqa: BLE001
                print(f"    {url}: {error}")
                continue
            extension = image_type(data)
            if extension is None:
                print(f"    {url}: kein Bild ({content_type})")
                continue
            path = os.path.join(folder, f"{index}.{extension}")
            with open(path, "wb") as file:
                file.write(data)
            saved.append({"file": path, "url": url, "type": content_type, "bytes": len(data)})
            print(f"    {index}.{extension} {len(data)} B  {url}")
        summary[identifier] = saved
    with open(os.path.join(target, "kandidaten.json"), "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], set(sys.argv[2:]))
