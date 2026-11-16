# subsy-web

Öffentliche Webseite für die iPhone App **Subsy**, gehostet mit GitHub Pages.

* `catalog/v1.json`: Anbieterkatalog mit Preisen und Wechselkursen. Die App lädt ihn von
  `https://aron5601.github.io/subsy-web/catalog/v1.json` (höchstens alle 12 Stunden) und
  hat eine mitgelieferte Kopie als Fallback.
* `index.html`: Startseite. Datenschutzerklärung und Support-Seite kommen dazu.
* `tools/validate_catalog.py`: prüft den Katalog. Läuft auch automatisch bei jedem Push (GitHub Actions).

## Preise anpassen

1. `catalog/v1.json` bearbeiten (direkt auf github.com mit dem Stift-Symbol geht auch).
2. Preise immer als Text mit Punkt: `"price": "13.90"`.
3. Nach dem Prüfen eines Preises `"priceCheckedOn": "2026-11-20"` setzen. `null` heisst ungeprüft,
   die App zeigt dann "Preis noch nicht geprüft".
4. `updatedAt` auf das heutige Datum setzen. Die App übernimmt nur einen Katalog, der nicht älter
   ist als der, den sie schon hat.
5. Prüfen: `python3 tools/validate_catalog.py catalog/v1.json`

Wechselkurse stehen unter `exchangeRates` (CHF pro EUR bzw. USD, als Text).

## Felder

| Feld | Bedeutung |
|---|---|
| `groups` | Gruppen vergleichbarer Dienste. `alternatives`: Anbieter sind austauschbar (Vorschlag "Günstigere Alternative"). `redundantIfMultiple`: mehrere Abos dieser Gruppe sind meistens doppelt. |
| `providers[].category` | Kategorie in der App: `streaming`, `music`, `mobileInternet`, `software`, `cloud`, `fitness`, `mobility`, `news`, `gaming`, `other` |
| `providers[].searchTerms` | Begriffe, an denen die App eigene Abos erkennt, klein geschrieben |
| `providers[].popular` | erscheint in der Schnellauswahl beim Erfassen |
| `plans[].tier` | Pläne mit gleicher Stufe bieten das Gleiche (z. B. `2tb`, `family`). Verglichen wird nur innerhalb derselben Stufe. |
| `plans[].maxPersons` | wie viele Personen den Plan teilen können (fehlt = 1) |
| `plans[].title` | optionaler Name für das Abo, sonst "Anbieter Plan" |
