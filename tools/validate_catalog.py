#!/usr/bin/env python3
"""Prüft den Anbieterkatalog für Subsy.

Aufruf: python3 tools/validate_catalog.py catalog/v1.json

Gibt alle Probleme aus und endet mit Fehlercode 1, wenn etwas nicht stimmt.
Die App selbst ist robust (ungültige Pläne werden ignoriert, ein kaputter Katalog
ersetzt den alten nicht), aber so fallen Tippfehler sofort auf.
"""
import json
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
        url = provider.get("url")
        if url is not None and urlparse(url).scheme != "https":
            issues.append(f"{pid}: URL muss mit https beginnen")
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
    unchecked = sum(1 for p in providers for plan in p["plans"] if plan.get("priceCheckedOn") is None)
    print(f"OK: {len(providers)} Anbieter, {plans} Pläne, davon {unchecked} noch ungeprüft.")


if __name__ == "__main__":
    main()
