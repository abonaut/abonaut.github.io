# Monatliche Preisprüfung

Anleitung für die regelmässige Prüfung von `catalog/v1.json`. Sie ist so geschrieben, dass
ein automatischer Agent (Claude Routine) sie Schritt für Schritt ausführen kann. Ein Mensch
kann ihr genauso folgen.

## Ziel

Jeder Plan im Katalog soll einen Preis haben, der höchstens 6 Monate alt geprüft ist.
Die App nutzt für Sparvorschläge **nur** Pläne mit `priceCheckedOn` in den letzten 180 Tagen.
Ungeprüfte oder veraltete Preise schaden also nicht, sie fehlen nur bei den Vorschlägen.

## Regeln

1. **Welcher Preis zählt:** der reguläre Preis, den eine neue Privatkundin in der Schweiz
   pro Abrechnung bezahlt. Ohne zeitlich begrenzte Aktionen ("12 Monate für …",
   "erster Monat gratis"). Ein Rabatt, der ohne Ablaufdatum gilt ("lebenslang"), zählt
   als regulärer Preis.
2. **Quellen in dieser Reihenfolge:**
   1. Offizielle Seite des Anbieters für die Schweiz (z. B. `apple.com/chde`, `spotify.com/ch-de`, `salt.ch`).
   2. Offizielle Preisinfo oder Medienmitteilung des Anbieters zu Preisänderungen.
   3. Zwei unabhängige Schweizer Vergleichsseiten, die übereinstimmen und datiert sind
      (z. B. comparis.ch, moneyland.ch). Eine einzelne Vergleichsseite reicht nicht.
   Deal-Seiten, Blogs und ausländische Seiten (Deutschland, USA) sind keine Quelle.
3. **Nur bei Gewissheit eintragen:** Wenn die Quellen widersprechen oder unklar ist, ob ein
   Preis aktuell ist, den Preis **nicht** ändern und `priceCheckedOn` **nicht** setzen.
   Lieber ungeprüft lassen als falsch prüfen.
4. **Angekündigte Preisänderungen:** Gilt ein neuer Preis erst ab einem späteren Datum,
   bis dahin den aktuellen Preis lassen. Im Pull Request vermerken, ab wann der neue gilt.
5. **Geprüfte Pläne:** `price` anpassen, `priceCheckedOn` auf das heutige Datum
   (`JJJJ-MM-TT`) setzen und beim Anbieter `priceSource` auf die verwendete Seite setzen.
6. **Pläne, die es nicht mehr gibt:** entfernen. Neue, wichtige Pläne dürfen dazukommen,
   mit eindeutiger `id`. Bestehende `id`s nie umbenennen, die App verknüpft Abos darüber.
7. **Wechselkurse:** `exchangeRates.ratesToCHF` für EUR und USD aktualisieren (Mittelkurs,
   3 Nachkommastellen genügen), `exchangeRates.date` auf das Datum der Kurse.
8. **Zum Schluss:** `updatedAt` auf das heutige Datum setzen und
   `python3 tools/validate_catalog.py catalog/v1.json --list-unchecked` ausführen.
   Es darf kein Fehler kommen.

## Ergebnis

Änderungen in einem eigenen Branch `preispruefung-JJJJ-MM` committen und als Pull Request
auf `main` öffnen. Der Pull Request enthält eine Tabelle:

| Anbieter | Plan | Alt | Neu | Quelle |
|---|---|---|---|---|

und darunter die Liste der Pläne, die ungeprüft geblieben sind, mit kurzem Grund
(z. B. "Seite zeigt keinen Preis ohne Anmeldung", "Quellen widersprechen sich").

Nicht direkt auf `main` committen. Ein Mensch schaut den Pull Request an und übernimmt ihn
mit "Merge". Erst dann sehen die Nutzerinnen und Nutzer die neuen Preise (die App lädt den
Katalog höchstens alle 12 Stunden neu).
