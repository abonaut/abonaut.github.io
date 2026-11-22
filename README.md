# subsy-web

Öffentliche Webseite für die iPhone App **Abonaut**, gehostet mit GitHub Pages.

* `catalog/v1.json`: Anbieterkatalog mit Preisen und Wechselkursen. Die App lädt ihn von
  `https://abonaut.github.io/catalog/v1.json` (höchstens alle 12 Stunden) und
  hat eine mitgelieferte Kopie als Fallback.
* `index.html`, `datenschutz.html`, `support.html`: Startseite, Datenschutz und Hilfe auf Deutsch. Übersetzungen in
  `fr/`, `it/` und `en/` (gleiche Dateinamen). Bei Änderungen alle vier Sprachen nachführen.
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
| `providers[].category` | Kategorie in der App: `streaming`, `music`, `mobileInternet`, `software`, `cloud`, `fitness`, `mobility`, `news`, `gaming`, `insurance`, `other`. `insurance` gibt es ab Version 1.1 der App, Version 1.0 zeigt solche Anbieter unter «Sonstiges». |
| `providers[].plans` | Pläne mit Preis. **Immer vorhanden.** Hängt der Preis vom Vertrag ab (Krankenkassen, Versicherungen), steht `"plans": []`. Nie weglassen: Fehlt das Feld bei einem einzigen Anbieter, verwirft Version 1.0 der App den ganzen Katalog. |
| `providers[].cancellation`, `groups[].cancellation` | Wie man kündigt, siehe «Kündigung» unten. Bei der Gruppe steht eine Regel, die für alle ihre Anbieter gilt (zum Beispiel die gesetzliche Frist der Grundversicherung). |
| `plans[].priceChange` | Angekündigter Preis: `price`, `from` (erster Tag, `JJJJ-MM-TT`), `source` (https), `checkedOn`. Ab `from` nimmt die App den neuen Preis von selbst. |
| `events` | Termine mit festem Datum, siehe «Termine» unten. |
| `providers[].summaryI18n`, `groups[].nameI18n` | Übersetzungen für `fr`, `it`, `en` (fehlt eine, zeigt die App Deutsch) |
| `providers[].nameI18n` | Übersetzter Anbietername, nur wo der Name mehr als eine Marke ist («CSS Grundversicherung» → «CSS assurance de base»). Ab Version 1.1 der App, Version 1.0 überspringt das Feld. Die Zuordnung eigener Abos läuft weiter über `searchTerms` und den deutschen `name`. |
| `providers[].summary` | kurze Beschreibung für den Tab «Entdecken», höchstens 60 Zeichen |
| `providers[].partnerURL` | Partnerlink (Affiliate, https). Ist er gesetzt, öffnet «Entdecken» ihn statt `url` und kennzeichnet ihn als Werbung. Erst eintragen, wenn das Partnerprogramm bestätigt ist. |
| `providers[].priceSource` | Seite, auf der die geprüften Preise stehen (Pflicht, sobald ein Plan geprüft ist) |
| `providers[].searchTerms` | Begriffe, an denen die App eigene Abos erkennt, klein geschrieben |
| `providers[].popular` | erscheint in der Schnellauswahl beim Erfassen |
| `plans[].tier` | Pläne mit gleicher Stufe bieten das Gleiche (z. B. `2tb`, `family`). Verglichen wird nur innerhalb derselben Stufe. |
| `plans[].maxPersons` | wie viele Personen den Plan teilen können (fehlt = 1) |
| `plans[].title` | optionaler Name für das Abo, sonst "Anbieter Plan" |

## Was Version 1.0 der App verlangt

Version 1.0 liest denselben Katalog. Sie überspringt Felder, die sie nicht kennt, und zeigt eine unbekannte Kategorie als
«Sonstiges». Sie verwirft aber den **ganzen** Katalog, wenn ein Feld fehlt oder einen anderen Typ hat, das sie verlangt:

* Katalog: `schemaVersion` (bleibt 1), `updatedAt`, `groups`, `providers`
* Gruppe: `id`, `name`, `alternatives`, `redundantIfMultiple`
* Anbieter: `id`, `name`, `category`, `searchTerms`, `plans`
* Plan: `id`, `name`, `price`, `currency`, `interval` mit `unit` und `count`

Deshalb: Neues nur als zusätzliches, optionales Feld. Nichts umbenennen, nichts entfernen, keinen Typ ändern.
`tools/validate_catalog.py` prüft das (`legacy_issues`), und in der App liest ein Test den Katalog mit einer eingefrorenen
Kopie des Lesers von 1.0. Einen Anbieter ohne Pläne lässt Version 1.0 einfach weg.

## Kündigung

Block `cancellation` beim Anbieter oder bei der Gruppe. Alles ist freiwillig, aber **nichts ohne Quelle**: Eingetragen wird
nur, was auf der offiziellen Seite des Anbieters (oder einer Stelle des Bundes) steht und dort selbst gelesen wurde.
Ohne `source` und `checkedOn` zeigt die App den Block nicht. Was sich nicht belegen lässt, bleibt weg.

| Feld | Bedeutung |
|---|---|
| `possible` | `false`, wenn sich der Vertrag nicht kündigen lässt (Serafe). Sonst weglassen. |
| `methods` | Wege, die der Anbieter für die Kündigung nennt, der empfohlene zuerst: `online`, `app`, `phone`, `chat`, `email`, `letter`, `counter` |
| `address` | Postadresse für den Brief, eine Zeile pro Eintrag (2 bis 6). Nur wenn der Anbieter sie ausdrücklich für Kündigungen nennt, nicht die allgemeine Firmenadresse. |
| `email`, `phone` | Nur wenn der Anbieter Kündigungen auf diesem Weg annimmt |
| `url` | Seite, auf der man kündigt oder auf der die Kündigung erklärt ist (https) |
| `notice` | Frist: `count` und `unit` (`day`, `week`, `month`, `year`), dazu `to`: `periodEnd` (Ende der bezahlten Periode), `monthEnd`, `yearEnd` (Ende Kalenderjahr), `termEnd` (Ende der Vertragsdauer), `anyDay`. `count` 0 = jederzeit. `receiptCounts: true`, wenn ausdrücklich der Eingang zählt. |
| `minimumTerm` | Mindestvertragsdauer, `count` und `unit` |
| `note`, `noteI18n` | Kurzer Hinweis für das, was nicht in die Felder passt, höchstens 260 Zeichen. Mit `note` sind alle drei Übersetzungen Pflicht. |
| `source`, `checkedOn` | Seite, die die Angaben belegt (https), und Datum der Prüfung. Pflicht. |

Krankenkassen stehen zweimal im Katalog: `<kasse>-grund` (Gruppe `krankenkasse-grund`) und `<kasse>-zusatz` (Gruppe
`krankenkasse-zusatz`). Der blosse Name der Kasse ist Suchbegriff der Grundversicherung. Die gesetzliche Frist der
Grundversicherung steht einmal bei der Gruppe.

## Termine

`events` ist eine Liste von Terminen mit festem Datum, die Abos einer Gruppe oder einzelner Anbieter betreffen:
`id`, `date` (`JJJJ-MM-TT`), `kind` (`deadline` = bis dann muss etwas erledigt sein, `info` = Hinweis), `groups` und/oder
`providers`, `title` und `text` mit `titleI18n` und `textI18n` (alle drei Sprachen sind Pflicht), `source` (https).
Jedes Jahr die Termine des nächsten Jahres nachtragen, sobald eine Quelle sie belegt. Vergangene Termine dürfen bleiben,
die App zeigt nur künftige.
