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
   bis dahin den aktuellen Preis in `price` lassen und den neuen beim Plan als `priceChange`
   eintragen: `{"price": "4095.00", "from": "2026-12-13", "source": "https://…", "checkedOn": "JJJJ-MM-TT"}`.
   `from` ist der erste Tag mit dem neuen Preis, `source` die offizielle Seite mit der Ankündigung.
   Ist das Datum erreicht: den neuen Preis nach `price` übernehmen, `priceCheckedOn` setzen und
   `priceChange` entfernen (die App rechnet ab dem Stichtag von selbst mit dem neuen Preis).
5. **Geprüfte Pläne:** `price` anpassen, `priceCheckedOn` auf das heutige Datum
   (`JJJJ-MM-TT`) setzen und beim Anbieter `priceSource` auf die verwendete Seite setzen.
6. **Pläne, die es nicht mehr gibt:** entfernen. Neue, wichtige Pläne dürfen dazukommen,
   mit eindeutiger `id`. Bestehende `id`s nie umbenennen, die App verknüpft Abos darüber.
7. **Wechselkurse:** nicht anfassen. Die GitHub Action "Wechselkurse aktualisieren" setzt sie jeden
   Samstag automatisch auf die Referenzkurse der EZB.
8. **Anbieter ohne Pläne:** Krankenkassen und Versicherungen haben `"plans": []`, weil der Preis vom
   Vertrag abhängt. Dort gibt es nichts zu prüfen. Das Feld `plans` nie entfernen, auch nicht leer:
   Version 1.0 der App verwirft sonst den ganzen Katalog.
9. **Kündigungsangaben (`cancellation`):** Bei jedem Anbieter mit einem solchen Block die Seite in
   `source` öffnen und prüfen, ob Wege, Adresse, E-Mail, Telefon und Frist noch so dort stehen.
   * Stimmt alles: nur `checkedOn` auf heute setzen.
   * Hat sich etwas geändert: Feld anpassen. Steht eine Angabe nicht mehr auf der Seite: Feld entfernen.
   * Nur die offizielle Schweizer Seite des Anbieters oder eine Stelle des Bundes (admin.ch, ch.ch,
     priminfo.admin.ch) zählt. Keine Kündigungsdienste, Vergleichsseiten, Blogs oder Foren.
   * Eine Adresse nur eintragen, wenn der Anbieter sie ausdrücklich für Kündigungen nennt. Die
     allgemeine Firmenadresse aus dem Impressum ist keine Kündigungsadresse.
   * Neue Angaben für Anbieter ohne Block dürfen dazukommen, nach denselben Regeln. Nichts aus dem
     Gedächtnis, nichts aus Suchergebnis-Schnipseln: Die Seite muss gelesen sein.
   * Die Felder stehen im README unter «Kündigung». `python3 tools/validate_catalog.py --list-open`
     zeigt die Anbieter ohne Angaben.
10. **Termine (`events`):** Im Herbst die Termine der Grundversicherung für das nächste Jahr nachtragen
    (Kündigung auf Ende Juni: Eingang bis 31. März; neue Prämie mitgeteilt bis 31. Oktober; Kündigung
    auf Ende Jahr: Eingang am letzten Arbeitstag im November). Quelle: priminfo.admin.ch oder das BAG.
    Fällt der Tag auf ein Wochenende, den letzten Arbeitstag davor eintragen. Alle Texte in vier Sprachen.
11. **Zum Schluss:** `updatedAt` auf das heutige Datum setzen und
    `python3 tools/validate_catalog.py catalog/v1.json --list-unchecked` ausführen.
    Es darf kein Fehler kommen.

## Ergebnis

Änderungen in einem eigenen Branch `preispruefung-JJJJ-MM` committen und als Pull Request
auf `main` öffnen. Der Pull Request enthält eine Tabelle:

| Anbieter | Plan | Alt | Neu | Quelle |
|---|---|---|---|---|

und darunter die Liste der Pläne, die ungeprüft geblieben sind, mit kurzem Grund
(z. B. "Seite zeigt keinen Preis ohne Anmeldung", "Quellen widersprechen sich").
Geänderte Kündigungsangaben, angekündigte Preise und neue Termine stehen in einer zweiten Liste,
je mit der Seite, auf der sie stehen.

Nicht direkt auf `main` committen. Ein Mensch schaut den Pull Request an und übernimmt ihn
mit "Merge". Erst dann sehen die Nutzerinnen und Nutzer die neuen Preise (die App lädt den
Katalog höchstens alle 12 Stunden neu).
