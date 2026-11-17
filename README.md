# subsy-web

Öffentliche Webseite für die iPhone App **Subsy**, gehostet mit GitHub Pages.

* `catalog/v1.json`: Anbieterkatalog mit Preisen und Wechselkursen. Die App lädt ihn von
  `https://aron5601.github.io/subsy-web/catalog/v1.json` (höchstens alle 12 Stunden) und
  hat eine mitgelieferte Kopie als Fallback.
* `index.html`: Startseite. Datenschutzerklärung und Support-Seite kommen dazu.
* `tools/validate_catalog.py`: prüft den Katalog. Läuft auch automatisch bei jedem Push (GitHub Actions).
* `tools/update_rates.py`: holt die Wechselkurse der EZB, läuft jeden Samstag automatisch.
* `logos/v1.json`: Logo-Paket für die App (siehe unten).

## Preise anpassen

1. `catalog/v1.json` bearbeiten (direkt auf github.com mit dem Stift-Symbol geht auch).
2. Preise immer als Text mit Punkt: `"price": "13.90"`.
3. Nach dem Prüfen eines Preises `"priceCheckedOn": "2026-11-20"` setzen und beim Anbieter
   `priceSource` auf die Seite, auf der der Preis steht. `null` heisst ungeprüft.
   Die App nutzt für Sparvorschläge nur Preise, die in den letzten 180 Tagen geprüft wurden.
   Die Regeln für die Prüfung stehen in [tools/PREISPRUEFUNG.md](tools/PREISPRUEFUNG.md).
4. `updatedAt` auf das heutige Datum setzen. Die App übernimmt nur einen Katalog, der nicht älter
   ist als der, den sie schon hat.
5. Prüfen: `python3 tools/validate_catalog.py catalog/v1.json`

Wechselkurse stehen unter `exchangeRates` (CHF pro EUR bzw. USD, als Text). Sie werden jeden Samstag
automatisch mit den Referenzkursen der Europäischen Zentralbank aktualisiert (GitHub Action
`.github/workflows/rates.yml`, Skript `tools/update_rates.py`). Von Hand auslösen: auf github.com
unter *Actions → Wechselkurse aktualisieren → Run workflow*. Springt ein Kurs um mehr als 25 %,
übernimmt das Skript ihn nicht und die Action schlägt fehl (GitHub schickt dann eine E-Mail).

## Logos

Die App zeigt bei bekannten Anbietern das Logo statt des Monogramms, auch für Abos, die nicht im Katalog stehen
(zum Beispiel eine Krankenkasse aus dem Kontoauszug-Import). Alle Logos stecken in einem Paket (`logos/v1.json`,
PNG als Base64, höchstens 144 x 144 Pixel, je mit Suchbegriffen). Die App lädt immer das ganze Paket, so erfährt
niemand, welche Abos jemand hat. Im Katalog steht unter `logos` die Version (Prüfsumme) und der Pfad. Ändert sich
die Version, lädt die App das Paket neu. Logos lassen sich in der App abschalten.

Zuordnung in der App: zuerst über die ID des Katalog-Anbieters, sonst über die Suchbegriffe als ganze Wörter im Namen
und Anbieter des Abos. Der längste Begriff gewinnt ("coop mobile" vor "coop").

* `logos/brands.json`: Marken ausserhalb des Katalogs mit ID, Name, Domain und Suchbegriffen. Suchbegriffe klein und
  eindeutig wählen (nicht "max" oder "uber", sondern "hbo max", "uber eats"). Bei Katalog-Anbietern kommen die
  Suchbegriffe aus `catalog/v1.json`.
* `logos/src/` (Originaldateien) und `logos/sources.json` (welche Datei zu welcher ID, woher sie stammt, optional
  `padding` für Logos ohne eigenen Rand).
* Neue Logos suchen: Marke in `logos/brands.json` eintragen, dann `python3 -I tools/fetch_logos.py <Ordner> <id>`.
  Das Skript holt das App-Symbol von der Website (oder über den Favicon-Dienst von Google) und wählt das grösste
  Bild ab 96 Pixel. `contact.html` im Ordner zeigt die Auswahl. Passt sie, mit `--apply` übernehmen.
  Findet das Skript nichts, eignen sich Logos von Wikimedia Commons (Quelle in `sources.json` angeben).
* Paket bauen (auf einem Mac): `python3 -I tools/build_logos.py`. Das Skript trägt die neue Version im Katalog ein
  und setzt `updatedAt` auf heute.
* Logo entfernen (zum Beispiel auf Wunsch eines Anbieters): Eintrag aus `logos/sources.json` löschen, Paket bauen,
  committen. Ein App-Update ist nicht nötig.
* Bewusst ohne Logo: Apple TV, Apple Music und iCloud+ (Apple erlaubt Dritten das Apple-Logo nicht).
* Die Logos sind Marken der jeweiligen Anbieter. Sie zeigen nur, um welchen Dienst es geht.

## Felder

| Feld | Bedeutung |
|---|---|
| `groups` | Gruppen vergleichbarer Dienste. `alternatives`: Anbieter sind austauschbar (Vorschlag "Günstigere Alternative"). `redundantIfMultiple`: mehrere Abos dieser Gruppe sind meistens doppelt. |
| `providers[].category` | Kategorie in der App: `streaming`, `music`, `mobileInternet`, `software`, `cloud`, `fitness`, `mobility`, `news`, `gaming`, `other` |
| `providers[].summary` | kurze Beschreibung für den Tab «Entdecken», höchstens 60 Zeichen |
| `providers[].partnerURL` | Partnerlink (Affiliate, https). Ist er gesetzt, öffnet «Entdecken» ihn statt `url` und kennzeichnet ihn als Werbung. Erst eintragen, wenn das Partnerprogramm bestätigt ist. |
| `providers[].priceSource` | Seite, auf der die geprüften Preise stehen (Pflicht, sobald ein Plan geprüft ist) |
| `providers[].searchTerms` | Begriffe, an denen die App eigene Abos erkennt, klein geschrieben |
| `providers[].popular` | erscheint in der Schnellauswahl beim Erfassen |
| `plans[].tier` | Pläne mit gleicher Stufe bieten das Gleiche (z. B. `2tb`, `family`). Verglichen wird nur innerhalb derselben Stufe. |
| `plans[].maxPersons` | wie viele Personen den Plan teilen können (fehlt = 1) |
| `plans[].title` | optionaler Name für das Abo, sonst "Anbieter Plan" |
