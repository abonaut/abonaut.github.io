#!/usr/bin/env python3
"""Prüft den Anbieterkatalog für Abonaut.

Aufruf: python3 tools/validate_catalog.py catalog/v1.json

Gibt alle Probleme aus und endet mit Fehlercode 1, wenn etwas nicht stimmt.
Die App selbst ist robust (ungültige Pläne werden ignoriert, ein kaputter Katalog
ersetzt den alten nicht), aber so fallen Tippfehler sofort auf.

Wichtig: Version 1.0 der App liest diesen Katalog auch. Sie überspringt Felder, die sie nicht
kennt, verwirft aber den GANZEN Katalog, wenn ein Feld fehlt, das sie verlangt, oder wenn ein
Feld einen anderen Typ hat als erwartet. Das prüft `legacy_issues`.
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
              "mobility", "news", "gaming", "insurance", "other"}
CURRENCIES = {"CHF", "EUR", "USD"}
UNITS = {"day", "week", "month", "year"}
LANGUAGES = ("fr", "it", "en")
# Wege, auf denen ein Anbieter die Kündigung annimmt, und worauf eine Kündigungsfrist wirkt.
METHODS = {"online", "app", "phone", "chat", "email", "letter", "counter"}
NOTICE_TARGETS = {"periodEnd", "monthEnd", "yearEnd", "termEnd", "anyDay"}
EVENT_KINDS = {"deadline", "info"}
MAX_NOTE = 260
DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
PRICE = re.compile(r"^\d+(\.\d{1,2})?$")
RATE = re.compile(r"^\d+(\.\d+)?$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9][0-9 ]{4,20}$")
LOGO_VERSION = re.compile(r"^[a-z0-9-]{4,64}$")
LOGO_PATH = re.compile(r"^logos/[a-z0-9._-]+\.json$")
SITE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def is_https(value):
    return isinstance(value, str) and urlparse(value).scheme == "https" and bool(urlparse(value).netloc)


def is_date(value):
    return isinstance(value, str) and bool(DATE.match(value))


def translations_ok(value, required=False, limit=None):
    """Übersetzungen für fr, it, en. `required`: alle drei müssen da sein."""
    if not isinstance(value, dict) or not set(value) <= set(LANGUAGES):
        return False
    if required and set(value) != set(LANGUAGES):
        return False
    return all(isinstance(text, str) and text and (limit is None or len(text) <= limit) for text in value.values())


def legacy_issues(catalog):
    """Was Version 1.0 der App verlangt. Jeder Fehler hier macht den ganzen Katalog für 1.0 unlesbar."""
    issues = []

    def need(owner, obj, key, kind, optional=False, nullable=False):
        if key not in obj:
            if not optional:
                issues.append(f"{owner}: {key} fehlt (Version 1.0 verwirft sonst den ganzen Katalog)")
            return
        value = obj[key]
        if value is None and (optional or nullable):
            return
        # bool ist in Python auch int, deshalb getrennt prüfen.
        wrong = isinstance(value, bool) != (kind is bool) or not isinstance(value, kind)
        if wrong:
            issues.append(f"{owner}: {key} hat den falschen Typ (Version 1.0 verwirft sonst den ganzen Katalog)")

    def string_map(owner, obj, key):
        value = obj.get(key)
        if value is not None and (not isinstance(value, dict) or not all(isinstance(v, str) for v in value.values())):
            issues.append(f"{owner}: {key} muss Texte enthalten (Version 1.0 verwirft sonst den ganzen Katalog)")

    need("Katalog", catalog, "schemaVersion", int)
    need("Katalog", catalog, "updatedAt", str)
    need("Katalog", catalog, "groups", list)
    need("Katalog", catalog, "providers", list)
    rates = catalog.get("exchangeRates")
    if rates is not None:
        if not isinstance(rates, dict):
            issues.append("exchangeRates muss ein Objekt sein")
        else:
            need("exchangeRates", rates, "date", str)
            need("exchangeRates", rates, "ratesToCHF", dict)
            string_map("exchangeRates", rates, "ratesToCHF")
    logos = catalog.get("logos")
    if logos is not None:
        if not isinstance(logos, dict):
            issues.append("logos muss ein Objekt sein")
        else:
            need("logos", logos, "version", str)
            need("logos", logos, "path", str)

    for group in catalog.get("groups") or []:
        if not isinstance(group, dict):
            issues.append("Gruppe ist kein Objekt (Version 1.0 verwirft sonst den ganzen Katalog)")
            continue
        owner = f"Gruppe {group.get('id', '?')}"
        need(owner, group, "id", str)
        need(owner, group, "name", str)
        need(owner, group, "alternatives", bool)
        need(owner, group, "redundantIfMultiple", bool)
        string_map(owner, group, "nameI18n")

    for provider in catalog.get("providers") or []:
        if not isinstance(provider, dict):
            issues.append("Anbieter ist kein Objekt (Version 1.0 verwirft sonst den ganzen Katalog)")
            continue
        owner = str(provider.get("id", "?"))
        need(owner, provider, "id", str)
        need(owner, provider, "name", str)
        need(owner, provider, "category", str)
        need(owner, provider, "searchTerms", list)
        need(owner, provider, "plans", list)
        for key in ("summary", "group", "url", "partnerURL"):
            need(owner, provider, key, str, optional=True)
        need(owner, provider, "popular", bool, optional=True)
        string_map(owner, provider, "summaryI18n")
        string_map(owner, provider, "nameI18n")
        if isinstance(provider.get("searchTerms"), list) and not all(isinstance(t, str) for t in provider["searchTerms"]):
            issues.append(f"{owner}: searchTerms muss Texte enthalten (Version 1.0 verwirft sonst den ganzen Katalog)")
        for plan in provider.get("plans") if isinstance(provider.get("plans"), list) else []:
            if not isinstance(plan, dict):
                issues.append(f"{owner}: Plan ist kein Objekt (Version 1.0 verwirft sonst den ganzen Katalog)")
                continue
            plan_owner = str(plan.get("id", "?"))
            need(plan_owner, plan, "id", str)
            need(plan_owner, plan, "name", str)
            need(plan_owner, plan, "price", str)
            need(plan_owner, plan, "currency", str)
            need(plan_owner, plan, "interval", dict)
            if isinstance(plan.get("interval"), dict):
                need(plan_owner, plan["interval"], "unit", str)
                need(plan_owner, plan["interval"], "count", int)
            for key in ("title", "tier"):
                need(plan_owner, plan, key, str, optional=True)
            need(plan_owner, plan, "maxPersons", int, optional=True)
            need(plan_owner, plan, "priceCheckedOn", str, optional=True)
            string_map(plan_owner, plan, "nameI18n")
            string_map(plan_owner, plan, "titleI18n")
    return issues


def validate_cancellation(block, owner):
    """Angaben zur Kündigung, beim Anbieter oder als Regel bei der Gruppe. Nichts ohne Quelle und Prüfdatum."""
    if not isinstance(block, dict):
        return [f"{owner}: cancellation muss ein Objekt sein"]
    issues = []
    known = {"possible", "methods", "address", "email", "url", "phone", "notice", "minimumTerm",
             "note", "noteI18n", "source", "checkedOn"}
    for key in sorted(set(block) - known):
        issues.append(f"{owner}: cancellation: unbekanntes Feld {key}")
    if not is_https(block.get("source")):
        issues.append(f"{owner}: cancellation: source (https) fehlt. Ohne Quelle zeigt die App nichts.")
    if not is_date(block.get("checkedOn")):
        issues.append(f"{owner}: cancellation: checkedOn muss JJJJ-MM-TT sein")
    if "possible" in block and not isinstance(block["possible"], bool):
        issues.append(f"{owner}: cancellation: possible muss true oder false sein")

    methods = block.get("methods")
    if methods is not None:
        if not isinstance(methods, list) or not methods or not set(methods) <= METHODS or len(set(methods)) != len(methods):
            issues.append(f"{owner}: cancellation: methods nur aus {sorted(METHODS)}, ohne Doppelte")
    address = block.get("address")
    if address is not None:
        if (not isinstance(address, list) or not 2 <= len(address) <= 6
                or not all(isinstance(line, str) and line.strip() == line and line for line in address)):
            issues.append(f"{owner}: cancellation: address braucht 2 bis 6 Zeilen ohne Leerzeilen")
    if "email" in block and not (isinstance(block["email"], str) and EMAIL.match(block["email"])):
        issues.append(f"{owner}: cancellation: email ungültig")
    if "url" in block and not is_https(block["url"]):
        issues.append(f"{owner}: cancellation: url muss mit https beginnen")
    if "phone" in block and not (isinstance(block["phone"], str) and PHONE.match(block["phone"])):
        issues.append(f"{owner}: cancellation: phone nur Ziffern, Leerzeichen und ein führendes +")

    notice = block.get("notice")
    if notice is not None:
        if (not isinstance(notice, dict) or isinstance(notice.get("count"), bool) or not isinstance(notice.get("count"), int)
                or not 0 <= notice["count"] <= 120 or notice.get("unit") not in UNITS):
            issues.append(f"{owner}: cancellation: notice braucht count (0 bis 120) und unit")
        else:
            if "to" in notice and notice["to"] not in NOTICE_TARGETS:
                issues.append(f"{owner}: cancellation: notice.to nur aus {sorted(NOTICE_TARGETS)}")
            if "receiptCounts" in notice and not isinstance(notice["receiptCounts"], bool):
                issues.append(f"{owner}: cancellation: notice.receiptCounts muss true oder false sein")
    term = block.get("minimumTerm")
    if term is not None:
        if (not isinstance(term, dict) or isinstance(term.get("count"), bool) or not isinstance(term.get("count"), int)
                or not 1 <= term["count"] <= 120 or term.get("unit") not in UNITS):
            issues.append(f"{owner}: cancellation: minimumTerm braucht count (1 bis 120) und unit")

    note = block.get("note")
    if note is not None:
        if not isinstance(note, str) or not 0 < len(note) <= MAX_NOTE:
            issues.append(f"{owner}: cancellation: note höchstens {MAX_NOTE} Zeichen")
        if not translations_ok(block.get("noteI18n"), required=True, limit=MAX_NOTE):
            issues.append(f"{owner}: cancellation: noteI18n braucht fr, it und en (höchstens {MAX_NOTE} Zeichen)")
    elif "noteI18n" in block:
        issues.append(f"{owner}: cancellation: noteI18n ohne note")

    has_content = block.get("possible") is False or any(
        key in block for key in ("methods", "address", "email", "url", "phone", "notice", "minimumTerm", "note"))
    if not has_content:
        issues.append(f"{owner}: cancellation: ohne Inhalt")
    if block.get("possible") is False and any(key in block for key in ("methods", "address", "notice")):
        issues.append(f"{owner}: cancellation: nicht kündbar, aber mit Weg, Adresse oder Frist")
    return issues


def validate_price_change(change, plan_id):
    """Angekündigter Preis: gilt ab `from`, in der Währung des Plans."""
    if not isinstance(change, dict):
        return [f"{plan_id}: priceChange muss ein Objekt sein"]
    issues = []
    if not PRICE.match(str(change.get("price", ""))) or not isinstance(change.get("price"), str):
        issues.append(f"{plan_id}: priceChange.price bitte als Text wie \"13.90\"")
    if not is_date(change.get("from")):
        issues.append(f"{plan_id}: priceChange.from muss JJJJ-MM-TT sein")
    if not is_https(change.get("source")):
        issues.append(f"{plan_id}: priceChange.source (https) fehlt")
    if not is_date(change.get("checkedOn")):
        issues.append(f"{plan_id}: priceChange.checkedOn muss JJJJ-MM-TT sein")
    return issues


def validate_events(catalog, group_ids, provider_ids):
    """Termine mit festem Datum, für Gruppen oder einzelne Anbieter, in allen vier Sprachen und mit Quelle."""
    events = catalog.get("events")
    if events is None:
        return []
    if not isinstance(events, list):
        return ["events muss eine Liste sein"]
    issues = []
    seen = set()
    for event in events:
        if not isinstance(event, dict):
            issues.append("Termin ist kein Objekt")
            continue
        eid = event.get("id", "?")
        if not isinstance(eid, str) or not re.match(r"^[a-z0-9-]{1,64}$", eid) or eid in seen:
            issues.append(f"Termin ohne gültige oder mit doppelter ID: {eid}")
        seen.add(eid)
        if not is_date(event.get("date")):
            issues.append(f"Termin {eid}: date muss JJJJ-MM-TT sein")
        if "kind" in event and event["kind"] not in EVENT_KINDS:
            issues.append(f"Termin {eid}: kind nur aus {sorted(EVENT_KINDS)}")
        groups = event.get("groups", [])
        providers = event.get("providers", [])
        if not isinstance(groups, list) or not isinstance(providers, list) or not (groups or providers):
            issues.append(f"Termin {eid}: braucht mindestens eine Gruppe oder einen Anbieter")
            continue
        for group in groups:
            if group not in group_ids:
                issues.append(f"Termin {eid}: unbekannte Gruppe {group}")
        for provider in providers:
            if provider not in provider_ids:
                issues.append(f"Termin {eid}: unbekannter Anbieter {provider}")
        if not isinstance(event.get("title"), str) or not 0 < len(event["title"]) <= 60:
            issues.append(f"Termin {eid}: title fehlt oder ist länger als 60 Zeichen")
        if not translations_ok(event.get("titleI18n"), required=True, limit=70):
            issues.append(f"Termin {eid}: titleI18n braucht fr, it und en (höchstens 70 Zeichen)")
        if "text" in event:
            if not isinstance(event["text"], str) or not 0 < len(event["text"]) <= 200:
                issues.append(f"Termin {eid}: text höchstens 200 Zeichen")
            if not translations_ok(event.get("textI18n"), required=True, limit=230):
                issues.append(f"Termin {eid}: textI18n braucht fr, it und en (höchstens 230 Zeichen)")
        elif "textI18n" in event:
            issues.append(f"Termin {eid}: textI18n ohne text")
        if not is_https(event.get("source")):
            issues.append(f"Termin {eid}: source (https) fehlt")
    return issues


def validate(catalog):
    issues = legacy_issues(catalog)
    if issues:
        # Ohne die Grundform lohnt sich der Rest nicht, und die Prüfungen unten könnten abstürzen.
        return issues
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
        if "cancellation" in group:
            issues += validate_cancellation(group["cancellation"], f"Gruppe {gid}")

    seen = set()
    provider_ids = set()
    providers = catalog.get("providers", [])
    if not providers:
        issues.append("Keine Anbieter")
    if not any(provider.get("plans") for provider in providers):
        issues.append("Kein Anbieter mit Plänen (Version 1.0 der App braucht mindestens einen)")
    for provider in providers:
        pid = provider.get("id", "?")
        if pid in seen:
            issues.append(f"Doppelte ID: {pid}")
        seen.add(pid)
        provider_ids.add(pid)
        if not provider.get("name"):
            issues.append(f"{pid}: name fehlt")
        if provider.get("category") not in CATEGORIES:
            issues.append(f"{pid}: unbekannte Kategorie {provider.get('category')}")
        if provider.get("group") is not None and provider["group"] not in group_ids:
            issues.append(f"{pid}: unbekannte Gruppe {provider['group']}")
        for key in ("summaryI18n", "nameI18n"):
            translations = provider.get(key)
            if translations is not None and not translations_ok(translations, limit=70):
                issues.append(f"{pid}: {key} braucht Texte für fr, it oder en (höchstens 70 Zeichen)")
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
        # Anbieter ohne Pläne sind erlaubt (Krankenkassen, Versicherungen: Der Preis hängt vom Vertrag ab).
        # Das Feld muss trotzdem da sein, als leere Liste (siehe legacy_issues).
        plans = provider.get("plans", [])
        if provider.get("popular") and not plans:
            issues.append(f"{pid}: Schnellauswahl (popular) braucht Pläne")
        if "cancellation" in provider:
            issues += validate_cancellation(provider["cancellation"], pid)
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
            for key in ("nameI18n", "titleI18n"):
                translations = plan.get(key)
                if translations is not None and (not isinstance(translations, dict) or not set(translations) <= {"fr", "it", "en"}):
                    issues.append(f"{plid}: {key} braucht Texte für fr, it oder en")
            if checked is not None and not DATE.match(str(checked)):
                issues.append(f"{plid}: priceCheckedOn muss null oder JJJJ-MM-TT sein")
            persons = plan.get("maxPersons")
            if persons is not None and (not isinstance(persons, int) or persons < 1):
                issues.append(f"{plid}: maxPersons muss eine ganze Zahl ab 1 sein")
            if "priceChange" in plan:
                issues += validate_price_change(plan["priceChange"], plid)
    issues += validate_events(catalog, group_ids, provider_ids)
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
    path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "catalog/v1.json"
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
    without_plans = sum(1 for p in providers if not p["plans"])
    with_cancellation = sum(1 for p in providers if "cancellation" in p)
    changes = sum(1 for p in providers for plan in p["plans"] if "priceChange" in plan)
    print(f"OK: {len(providers)} Anbieter ({without_plans} ohne Pläne), {plans} Pläne, "
          f"davon {plans - len(unchecked)} geprüft, {len(unchecked)} ungeprüft.")
    print(f"    Kündigung belegt bei {with_cancellation} Anbietern, {changes} angekündigte Preise, "
          f"{len(catalog.get('events', []))} Termine.")
    if "--list-unchecked" in sys.argv:
        for name in unchecked:
            print(f"  ungeprüft: {name}")
    if "--list-open" in sys.argv:
        for provider in providers:
            if "cancellation" not in provider:
                print(f"  ohne Kündigungsangaben: {provider['name']}")


if __name__ == "__main__":
    main()
