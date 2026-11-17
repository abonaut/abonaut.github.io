#!/usr/bin/env python3
"""Prüft den Anbieterkatalog für Subsy.

Aufruf: python3 tools/validate_catalog.py catalog/v1.json

Gibt alle Probleme aus und endet mit Fehlercode 1, wenn etwas nicht stimmt.
Die App selbst ist robust (ungültige Pläne werden ignoriert, ein kaputter Katalog
ersetzt den alten nicht), aber so fallen Tippfehler sofort auf.
"""
import base64
import hashlib
import json
import os
import re
import sys
from urllib.parse import urlparse

SCHEMA_VERSION = 1
CATEGORIES = {"streaming", "music", "mobileInternet", "software", "cloud", "fitness",
              "mobility", "news", "gaming", "other"}
CURRENCIES = {"CHF", "EUR", "USD"}
UNITS = {"day", "week", "month", "year"}
DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
PRICE = re.compile(r"^\d+(\.\d{1,2})?$")
RATE = re.compile(r"^\d+(\.\d+)?$")
LOGO_VERSION = re.compile(r"^[a-z0-9-]{4,64}$")
LOGO_PATH = re.compile(r"^logos/[a-z0-9._-]+\.json$")
SITE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def validate(catalog):
    issues = []
    if catalog.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(f"schemaVersion muss {SCHEMA_VERSION} sein")
    if not DATE.match(str(catalog.get("updatedAt", ""))):
        issues.append("updatedAt muss im Format JJJJ-MM-TT sein")

    rates = catalog.get("exchangeRates")
    if rates is not None:
        if not DATE.match(str(rates.get("date", ""))):
            issues.append("exchangeRates.date muss im Format JJJJ-MM-TT sein")
        for code in ("EUR", "USD"):
            if not RATE.match(str(rates.get("ratesToCHF", {}).get(code, ""))):
                issues.append(f"exchangeRates.ratesToCHF.{code} fehlt oder ist keine Zahl als Text")

    group_ids = set()
    for group in catalog.get("groups", []):
        gid = group.get("id")
        if not gid or gid in group_ids:
            issues.append(f"Gruppe ohne oder mit doppelter ID: {gid}")
        group_ids.add(gid)
        for key in ("name", "alternatives", "redundantIfMultiple"):
            if key not in group:
                issues.append(f"Gruppe {gid}: {key} fehlt")

    seen = set()
    providers = catalog.get("providers", [])
    if not providers:
        issues.append("Keine Anbieter")
    for provider in providers:
        pid = provider.get("id", "?")
        if pid in seen:
            issues.append(f"Doppelte ID: {pid}")
        seen.add(pid)
        if not provider.get("name"):
            issues.append(f"{pid}: name fehlt")
        if provider.get("category") not in CATEGORIES:
            issues.append(f"{pid}: unbekannte Kategorie {provider.get('category')}")
        if provider.get("group") is not None and provider["group"] not in group_ids:
            issues.append(f"{pid}: unbekannte Gruppe {provider['group']}")
        summary = provider.get("summary")
        if summary is not None and (not isinstance(summary, str) or not 0 < len(summary) <= 60):
            issues.append(f"{pid}: summary muss Text mit höchstens 60 Zeichen sein")
        for key in ("url", "priceSource", "partnerURL"):
            value = provider.get(key)
            if value is not None and urlparse(value).scheme != "https":
                issues.append(f"{pid}: {key} muss mit https beginnen")
        checked_plans = [plan for plan in provider.get("plans", []) if plan.get("priceCheckedOn")]
        if checked_plans and not provider.get("priceSource"):
            issues.append(f"{pid}: geprüfte Preise brauchen eine priceSource")
        terms = provider.get("searchTerms", [])
        if not terms:
            issues.append(f"{pid}: keine Suchbegriffe")
        if any(term != term.lower() for term in terms):
            issues.append(f"{pid}: Suchbegriffe bitte klein schreiben")
        plans = provider.get("plans", [])
        if not plans:
            issues.append(f"{pid}: keine Pläne")
        for plan in plans:
            plid = plan.get("id", "?")
            if plid in seen:
                issues.append(f"Doppelte ID: {plid}")
            seen.add(plid)
            if not plan.get("name"):
                issues.append(f"{plid}: name fehlt")
            if not PRICE.match(str(plan.get("price", ""))):
                issues.append(f"{plid}: Preis bitte als Text wie \"13.90\", gefunden: {plan.get('price')!r}")
            if plan.get("currency") not in CURRENCIES:
                issues.append(f"{plid}: Währung muss CHF, EUR oder USD sein")
            interval = plan.get("interval", {})
            if interval.get("unit") not in UNITS or not isinstance(interval.get("count"), int) or interval["count"] < 1:
                issues.append(f"{plid}: Intervall ungültig")
            checked = plan.get("priceCheckedOn")
            if checked is not None and not DATE.match(str(checked)):
                issues.append(f"{plid}: priceCheckedOn muss null oder JJJJ-MM-TT sein")
            persons = plan.get("maxPersons")
            if persons is not None and (not isinstance(persons, int) or persons < 1):
                issues.append(f"{plid}: maxPersons muss eine ganze Zahl ab 1 sein")
    issues += validate_logos(catalog, seen)
    return issues


def validate_logos(catalog, ids):
    """Der Block logos und das Paket daneben: gültige Version, Pfad, nur bekannte Anbieter, PNG-Daten."""
    logos = catalog.get("logos")
    if logos is None:
        return []
    issues = []
    version = str(logos.get("version", ""))
    path = str(logos.get("path", ""))
    if not LOGO_VERSION.match(version):
        issues.append("logos.version ungültig")
    if not LOGO_PATH.match(path):
        issues.append("logos.path muss wie logos/v1.json aussehen")
        return issues
    package_file = os.path.join(SITE_ROOT, path)
    if not os.path.isfile(package_file):
        return issues + [f"Logo-Paket fehlt: {path}"]
    with open(package_file, encoding="utf-8") as file:
        text = file.read()
    if hashlib.sha256(text.encode("utf-8")).hexdigest()[:12] != version:
        issues.append("logos.version passt nicht zum Paket (tools/build_logos.py ausführen)")
    package = json.loads(text)
    if package.get("schemaVersion") != 1:
        issues.append("Logo-Paket: schemaVersion muss 1 sein")
    brands_file = os.path.join(SITE_ROOT, "logos", "brands.json")
    brand_ids = set()
    if os.path.isfile(brands_file):
        with open(brands_file, encoding="utf-8") as file:
            brand_ids = {brand["id"] for brand in json.load(file)["brands"]}
    seen_logos = set()
    for entry in package.get("logos", []):
        identifier = entry.get("id", "?")
        if identifier in seen_logos:
            issues.append(f"Logo doppelt: {identifier}")
        seen_logos.add(identifier)
        if identifier not in ids and identifier not in brand_ids:
            issues.append(f"Logo für unbekannten Anbieter: {identifier}")
        if not re.match(r"^[a-z0-9-]{1,64}$", identifier):
            issues.append(f"Logo-ID ungültig: {identifier}")
        terms = entry.get("terms", [])
        if not terms or any(term != term.lower() for term in terms):
            issues.append(f"Logo {identifier}: Suchbegriffe fehlen oder sind nicht klein geschrieben")
        try:
            png = base64.b64decode(entry.get("png", ""), validate=True)
        except ValueError:
            issues.append(f"Logo {identifier}: kein gültiges Base64")
            continue
        if not png.startswith(b"\x89PNG") or len(png) > 80_000:
            issues.append(f"Logo {identifier}: kein PNG oder grösser als 80 KB")
    return issues


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "catalog/v1.json"
    try:
        with open(path, encoding="utf-8") as file:
            catalog = json.load(file)
    except json.JSONDecodeError as error:
        print(f"Kein gültiges JSON: {error}")
        sys.exit(1)

    issues = validate(catalog)
    if issues:
        print(f"{len(issues)} Problem(e) in {path}:")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)

    providers = catalog["providers"]
    plans = sum(len(p["plans"]) for p in providers)
    unchecked = [f"{p['name']} {plan['name']}" for p in providers for plan in p["plans"] if not plan.get("priceCheckedOn")]
    print(f"OK: {len(providers)} Anbieter, {plans} Pläne, davon {plans - len(unchecked)} geprüft, {len(unchecked)} ungeprüft.")
    if "--list-unchecked" in sys.argv:
        for name in unchecked:
            print(f"  ungeprüft: {name}")


if __name__ == "__main__":
    main()
