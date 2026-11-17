#!/usr/bin/env python3
"""Aktualisiert die Wechselkurse im Anbieterkatalog mit den Referenzkursen der EZB.

Aufruf:
  python3 tools/update_rates.py catalog/v1.json            # Kurse von der EZB holen
  python3 tools/update_rates.py catalog/v1.json --xml X    # Kurse aus einer lokalen Datei (zum Testen)
  python3 tools/update_rates.py catalog/v1.json --dry-run  # nur anzeigen, nichts schreiben

Die EZB veröffentlicht an jedem Arbeitstag um etwa 16 Uhr Referenzkurse pro Euro. Daraus wird
CHF pro EUR und CHF pro USD berechnet (4 Nachkommastellen). Geändert wird nur der Block
`exchangeRates`, der Rest der Datei bleibt Zeichen für Zeichen gleich. `updatedAt` bleibt ebenfalls,
die App übernimmt einen Katalog mit gleichem `updatedAt` trotzdem.

Schutz: Kurse ausserhalb von 0.3 bis 3 oder eine Änderung um mehr als 25 % seit dem letzten Stand
werden nicht übernommen (Fehlercode 1), damit ein Fehler bei der Quelle nie in die App gelangt.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
MIN_RATE = Decimal("0.3")
MAX_RATE = Decimal("3")
MAX_CHANGE = Decimal("0.25")
BLOCK = re.compile(r'"exchangeRates"\s*:\s*\{.*?"ratesToCHF"\s*:\s*\{.*?\}\s*\}', re.DOTALL)


def fetch_ecb_xml():
    request = urllib.request.Request(ECB_URL, headers={"User-Agent": "subsy-web rates updater"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def parse_ecb(xml_bytes):
    """Gibt (Datum, {Währung: Kurs pro EUR}) zurück."""
    root = ET.fromstring(xml_bytes)
    for element in root.iter():
        if element.get("time"):
            rates = {child.get("currency"): Decimal(child.get("rate")) for child in element if child.get("currency")}
            return element.get("time"), rates
    raise ValueError("Keine Kurse in der EZB-Datei gefunden")


def chf_rates(per_eur):
    """CHF pro EUR und CHF pro USD aus den Kursen pro Euro."""
    chf, usd = per_eur.get("CHF"), per_eur.get("USD")
    if chf is None or usd is None or usd == 0:
        raise ValueError("CHF oder USD fehlt in der EZB-Datei")
    step = Decimal("0.0001")
    return {
        "EUR": chf.quantize(step, ROUND_HALF_UP),
        "USD": (chf / usd).quantize(step, ROUND_HALF_UP),
    }


def check(new, old):
    problems = []
    for code, rate in new.items():
        if not MIN_RATE < rate < MAX_RATE:
            problems.append(f"{code}: Kurs {rate} ist unplausibel")
        previous = old.get(code)
        if previous:
            change = abs(rate - Decimal(previous)) / Decimal(previous)
            if change > MAX_CHANGE:
                problems.append(f"{code}: Änderung um {change:.0%} seit {previous}, bitte von Hand prüfen")
    return problems


def render_block(date, rates):
    return (
        '"exchangeRates": {\n'
        f'    "date": "{date}",\n'
        '    "ratesToCHF": {\n'
        f'      "EUR": "{rates["EUR"]}",\n'
        f'      "USD": "{rates["USD"]}"\n'
        '    }\n'
        '  }'
    )


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = argv[1]
    dry_run = "--dry-run" in argv
    xml_file = argv[argv.index("--xml") + 1] if "--xml" in argv else None

    raw = open(path, encoding="utf-8").read()
    catalog = json.loads(raw)
    old = (catalog.get("exchangeRates") or {}).get("ratesToCHF", {})

    xml_bytes = open(xml_file, "rb").read() if xml_file else fetch_ecb_xml()
    date, per_eur = parse_ecb(xml_bytes)
    rates = chf_rates(per_eur)

    problems = check(rates, old)
    if problems:
        print("Nicht übernommen:\n  " + "\n  ".join(problems))
        return 1

    if not BLOCK.search(raw):
        print("Block exchangeRates nicht gefunden")
        return 1
    updated = BLOCK.sub(lambda _: render_block(date, rates), raw, count=1)

    # Sicherheitsnetz: gültiges JSON, nur exchangeRates geändert.
    new_catalog = json.loads(updated)
    expected = dict(catalog, exchangeRates={"date": date, "ratesToCHF": {k: str(v) for k, v in rates.items()}})
    if new_catalog != expected:
        print("Unerwartete Änderung am Katalog, nichts geschrieben")
        return 1

    print(f"Kurse vom {date}: 1 EUR = CHF {rates['EUR']} (vorher {old.get('EUR')}), "
          f"1 USD = CHF {rates['USD']} (vorher {old.get('USD')})")
    if updated == raw:
        print("Keine Änderung")
    elif not dry_run:
        with open(path, "w", encoding="utf-8") as file:
            file.write(updated)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
