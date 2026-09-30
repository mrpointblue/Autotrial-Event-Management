# Autotrial · 0.1.0

Eigenständiges Schwesterprojekt der Quad Parallel Race Software: Nennung,
Papierbordkarten und nachträgliche Auswertung. Grundgerüst mit durchgängigem
Arbeitsablauf; noch keine abgenommene Turniersoftware.

## Docker-only starten

Docker Engine / Docker Desktop mit Compose ist die einzige Laufzeitvoraussetzung.

```sh
docker compose up -d --build --wait
```

Oberfläche: http://localhost:8020 · API-Dokumentation: http://localhost:8020/docs

Port 8020 vermeidet Konflikte mit Quad Race (8000/8010). Standardmäßig ist nur
lokaler Zugriff möglich. Für das vertrauenswürdige Veranstaltungsnetz `.env.example`
nach `.env` kopieren und `AUTOTRIAL_BIND=0.0.0.0` setzen. Noch keine Anmeldung oder
Rollenverwaltung; nicht öffentlich ins Internet stellen.

Ein Container enthält FastAPI, Jinja-Oberfläche und SQLite. Persistentes Volume
`autotrial_autotrial-data`. Kein Kiosk, kein Monitor, keine Zeitnahme, kein
Host-Updater, keine Hardwareberechtigungen. Der Veranstaltungsbetrieb benötigt
nach dem Image-Build kein Internet und keine externen Schriftarten/CDNs.

## Arbeitsablauf

1. Veranstaltung mit Anzahl Sektionen und Durchläufen anlegen.
2. Fahrer mit eindeutiger fester Startnummer und Fahrzeuge mit technischen Daten,
   Klasse und bestätigtem HCF anlegen.
3. Bekannte Fahrzeuge Fahrern zuordnen; optional eines als Standard setzen.
   Fahrzeuge können beliebig vielen Startnummern zugeordnet sein.
4. Nennung: Fahrer über Startnummer, Vor- oder Nachname suchen (auch kombiniert,
   unabhängig von der Namensreihenfolge) und tatsächlich verwendetes Fahrzeug auswählen. Name, Startnummer,
   vollständige Fahrzeugdaten, Klasse und HCF werden als Snapshot gespeichert.
   Ein Fahrer kann pro Veranstaltung nur einmal genannt werden.
5. Papier-/Unterschriftenprüfung und technische Abnahme bestätigen. Bezahlstatus
   separat erfassen. Anschließend Bordkarte im Browser drucken, bei Bedarf als PDF.
   Die Papierabnahme ersetzt keine erforderlichen Originalunterschriften.
6. Nach dem Event Startnummer eingeben und **Fehler1 und Fehler2 als Rohpunkte je Sektion**
   von den Karten übernehmen. Reihenfolge ist unabhängig von Klasse und Fahrzeug.
   Leere Werte bleiben offen, 0 zählt als erfasst. Zwischenstände sind erlaubt.
7. Klassenfortschritt bleibt neben der Eingabe sichtbar und aktualisiert sich alle
   fünf Sekunden. Fehlende Fahrer werden namentlich und mit Startnummer angezeigt.
   NiW mit Begründung zählt als bearbeitet; fehlende Karten ohne Entscheidung nicht.
8. Vollständige Klassen können gedruckt werden. Die Druckroute prüft die
   Vollständigkeit erneut. Gleichstände: 1, 1, 3 gemäß Reglement.

## Fachlich bewusst offen

**Nicht jede Fehlerart wird durch den HCF geteilt.** Ein einzelner Rohgesamtwert
pro Sektion reicht daher nicht für eine korrekte automatische HCF-Verrechnung.
Die Erfassung trennt Fehler1 (HCF-relevant) und Fehler2 (unverändert).
Gesamt = Summe Fehler1 / Nennungs-HCF + Summe Fehler2. Erst die Gesamtsumme
wird kaufmännisch auf zwei Nachkommastellen gerundet. Alte Endwerte bleiben erhalten
und werden niemals erneut durch den HCF geteilt.

Der HCF wird für Geländewagen, ATV und Quad automatisch aus den Maßen in ganzen
cm und den fahrzeugartspezifischen Korrekturen vorgeschlagen. Basisformel und
Prozentkorrekturen erscheinen direkt beim Anlegen. Korrekturen werden addiert,
anschließend auf die Basis angewandt. Der endgültige HCF wird kaufmännisch (ROUND_HALF_UP) auf zwei Nachkommastellen
gerundet. Zwischenwerte bleiben für die Berechnung ungerundet. Auch manuelle
Werte und neue Nennungs-Snapshots verwenden diese Rundung. Historische
Nennungs-Snapshots werden nicht nachträglich verändert.
Beim Speichern berechnet das Backend den Wert erneut. Eine manuelle Bestätigung
oder Korrektur benötigt einen positiven HCF und eine Begründung der technischen
Abnahme. Für Side-by-Side bleibt die Bestätigung manuell, da die vorliegende
Grundlage keine eindeutige Formel zuordnet. Die Klasse wird weiterhin durch die
Abnahme ausgewählt, nicht automatisch aus HCF-Grenzen abgeleitet.
Die Reglementformeln sind in `docs/rules-2026.md` dokumentiert.
Q-Minis steht im Nennformular, hat aber keine Regeldefinition im gelieferten
Reglement und ist deshalb noch nicht als Wertungsklasse aktiviert.

## Struktur

```text
backend/
  database.py           SQLite, Fremdschlüssel, WAL, Sessions
  models.py             Fahrer, Fahrzeug, Zuordnung, Event, Snapshot, Sektionswert
  schemas.py            validierte API-Eingaben
  main.py               API, HTML-Seiten und Druckrouten
  services/scoring.py   Vollständigkeit, NiW, 70-Prozent-Prüfung, Rangfolge
  templates/            Jinja-Seiten und Drucklayouts
  static/               lokales CSS / JavaScript
tests/                  API- und Fachlogiktests
docs/                   Datenmodell, Quellen, Entscheidungen
compose.yaml            persistenter Docker-Betrieb
.github/workflows/      Tests und Docker-Startprüfung bei Push/PR
```

Gleicher Basisstack und übernommene UI-Grundkomponenten wie
[mrpointblue/Quad-Racing-Software](https://github.com/mrpointblue/Quad-Racing-Software):
FastAPI, SQLAlchemy, SQLite, Jinja, dunkler Kopf-/Navigationsbereich, Karten,
Formular- und Tabellenstil. MIT-Hinweis erhalten. Fachmodelle wurden neu aufgebaut.
Keine Renn-, LOGO-, Monitor- oder Marshal-Module übernommen.

## Prüfen und sichern

Tests komplett in Docker:

```sh
docker build -t autotrial:0.1.0 .
docker run --rm -v "$PWD/tests:/app/tests:ro" -v "$PWD/requirements-dev.txt:/app/requirements-dev.txt:ro" --user root autotrial:0.1.0 sh -c 'pip install -r requirements-dev.txt && python -m pytest -q'
```

Der zusätzliche Paketdownload ist nur für Tests erforderlich. CI prüft zusätzlich
Compose-Konfiguration, Image-Build, Container-Healthcheck und HTTP-Erreichbarkeit.

Konsistente Sicherung (SQLite einschließlich WAL):

```sh
docker compose stop
docker compose cp app:/app/data ./backup-data
docker compose start
```

Sicherungen extern aufbewahren. `docker compose down` erhält das Volume;
`docker compose down -v` löscht es. Keine realen Teilnehmerdaten ins Repository.
Datenbankschema v4 ergänzt beim Start Fehlerfelder, Kontakt-Snapshots sowie Klassen und Mannschaften.
Bestehende Endwerte bleiben unverändert; es wird keine Fehleraufteilung erfunden.
Vor dem Update die oben beschriebene Datensicherung erstellen.

## Nächste Ausbaustufe

Original-Bordkartenlayout und Punkteformat abstimmen;  vollständige Stammdatenbearbeitung; fachliche Freigabe von Rundung und SbS-Formel; Anmeldung/Rollen und Sicherungsoberfläche; signierte Releases
und Images für amd64/arm64. Automatische Updates und GHCR-Publishing sind noch
nicht eingerichtet.

## Datenbankübersicht

Unter **Datenbank** stehen getrennte Fahrer- und Fahrzeugübersichten bereit.
Die Fahrerliste zeigt feste Startnummer, Verein, Standardfahrzeug, Klasse und HCF.
Die Fahrzeugliste zeigt Kennzeichen, Klasse, HCF und zugeordnete Fahrer;
geteilte Fahrzeuge erscheinen nur einmal. Kontakt- und Technikdetails sind
aufklappbar. Suche, Klassenfilter, Trefferzahl und Seiten mit je 25 Datensätzen
halten größere Bestände übersichtlich. Neue Datensätze und Zuordnungen haben
eigene Ansichten. HCF-Anzeigen verwenden zwei Nachkommastellen und Dezimalkomma.

## Nennung bearbeiten

In der Liste **Genannte Fahrer → Bearbeiten** können die Klasse für die aktuelle
Veranstaltung, das verwendete zugeordnete Fahrzeug, der bestätigte HCF, der
Beifahrer sowie Zahlung und Abnahme geändert werden. Ein Änderungsgrund ist
Pflicht; vorherige und neue Werte sowie UTC-Zeitpunkt werden protokolliert.
Feste Startnummer, Fahreridentität, Stammdaten und andere Nennungen bleiben gleich.

Ein reiner Klassenwechsel übernimmt vorhandene Sektionswerte und aktualisiert
Klassenfortschritt und Ranglisten sofort. Änderungen an HCF oder Fahrzeug setzen
bereits erfasste reguläre Wertungen auf offen; die Werte bleiben zum Abgleich
vorhanden und müssen unter **Bordkarten erfassen** geprüft und erneut gespeichert
werden. NiW bleibt eine eigenständige Entscheidung. Korrigierte Bordkarten neu
ausdrucken und die vorherige Karte ersetzen.

## Wertungspunkte nach Tabelle B

Ergebnisse und Ergebnisdruck zeigen neben den Gesamtfehlern die **Wertungspunkte B**:
`(80 − (Platz × 30) / (Teilnehmerzahl + 1)) × 10`, kaufmännisch auf ganze Punkte
gerundet. Die Teilnehmerzahl wird je Klasse einschließlich NiW ermittelt.
NiW erhält keine Punkte (Anzeige „—“). Gleiche Plätze erhalten dieselben Punkte.
Die Ergebnisseite zeigt vollständige Klassen als Tabellen und offene Klassen
mit ihren fehlenden Fahrern. Sie aktualisiert sich alle fünf Sekunden.

## Ergebnisdruck und Siegerehrung

Unter Ergebnisse: einzelne Klassen, alle Klassen für die Siegerehrung oder die
ADAC-Gesamtauswertung drucken bzw. im Druckdialog als PDF speichern. A4 quer,
MSC-Kopf und Tabelle orientieren sich an der bereitgestellten Ergebnisliste 2025.
Das MSC-Logo wurde aus dieser Vorlage übernommen. Namen bleiben als ein Feld
erhalten, damit mehrteilige Namen nicht falsch aufgeteilt werden.

Beim Siegerehrungsdruck beginnt jede Klasse auf einer eigenen Seite und wird
bei Bedarf auf die Seitenhöhe angepasst. Die ADAC-Liste läuft klassenweise über
mehrere Seiten, mit wiederholtem Tabellenkopf. Es gibt keine klassenübergreifende
Rangfolge. Gesamtdruck setzt vollständig erfasste Klassen voraus, einzelne fertige
Klassen können vorher gedruckt werden.

Fehler1 im Ausdruck ist bereits durch den Nennungs-HCF geteilt. Fehler2 bleibt
unverändert. Alte oder nur teilweise aufgeteilte Ergebnisse zeigen bei beiden
Fehlerarten einen Strich, behalten aber ihren Gesamtwert. NiW bleibt ohne Punkte.
Mannschaften werden aus drei bis fünf Startnummern genannt und über die besten drei Klassenpunktzahlen gewertet.

## Funktionsumfang der Excel-Auswertung

Die [Excel-Abgleichsdokumentation](docs/excel-parity.md) beschreibt die Funktionen
der bereitgestellten Auswertungsmappe und ihre Umsetzung. Neu sind konfigurierbare
Veranstaltungsklassen mit Sektionsgruppe/Pokalplanung, Fehleranzahl-Eingabe,
Mannschaftsnennung und automatische Best-drei-Wertung sowie Starterliste und
ADAC-CSV. Der ADAC-Druck enthält zusätzlich Anschrift, Verein und Mitgliedsnummer.

Bei der Nennung kann eine abweichende Veranstaltungsklasse gewählt werden.
Standardklassen bleiben als Ausgangspunkt erhalten, unbenutzte können entfernt
werden. Klassen mit Nennungen können erst nach deren Umzuordnung entfernt werden.
Eine neue Veranstaltung beginnt mit unabhängigen Klassen und Mannschaften.

## Startnummern, Fahrzeugkarten und Korrekturen

Beim Fahrer-Anlegen sind Startnummern von 1 bis 999 möglich. Ohne Eingabe wird
die kleinste freie Nummer vergeben; vorhandene Lücken werden wieder genutzt.
Die automatische Vergabe ist gegen gleichzeitige Registrierungen abgesichert.
Eine belegte oder außerhalb des Bereichs liegende Nummer wird zurückgewiesen.

In der Fahrerübersicht können alle zugeordneten Fahrzeugkarten gemeinsam oder
einzeln gedruckt werden. Jede Karte gehört zur Kombination aus Startnummer und
Fahrzeug. Zwei Fahrzeuge ergeben zwei Karten mit derselben Startnummer; ein
geteiltes Fahrzeug ergibt je Fahrer eine Karte mit dessen Startnummer. Format
85,6 × 53,98 mm, Druck mit 100 % / tatsächlicher Größe und ohne Browser-Kopfzeilen.

Unter Bordkarten erfassen führt „Klasse öffnen / bearbeiten“ zur Klassenübersicht.
Jede Nennung lässt sich erneut öffnen und korrigieren, einschließlich alter
Gesamtwerte und NiW. Nach dem Speichern werden Liste und Fortschritt aktualisiert.
Versionsprüfung schützt vor dem Überschreiben zwischenzeitlicher Änderungen.

## Einstellungen

Oben rechts führt „Einstellungen“ zu Zeit, Datenbank und Logo. Zeitzone sowie eine optional vom Browser oder manuell übernommene Anwendungszeit werden dauerhaft gespeichert. Die Rechner-/Docker-Hostzeit wird nicht verändert; SYS_TIME oder zusätzliche Containerrechte sind nicht erforderlich. „Wieder Rechnerzeit verwenden“ entfernt den Zeitversatz. Neue Änderungsprotokolle verwenden die Autotrial-Zeit, vorhandene Zeitstempel werden nur in der gewählten Zeitzone angezeigt.

Der Datenbankexport verwendet die SQLite-Backup-Schnittstelle und enthält auch Einstellungen und Logo. Der Import akzeptiert passende Exporte mit Schema 7 bis 100 MB. Vor dem Ersetzen wird unter `/app/data/backups` automatisch eine herunterladbare Sicherung angelegt. Ein fehlgeschlagener Import setzt die Datenbank aus dieser Sicherung zurück. Während eines Imports werden andere Anfragen zurückgestellt. **Die Anwendung muss mit einem Uvicorn-Worker betrieben werden**, wie in Dockerfile/Compose vorgegeben, damit die Importsperre alle Schreibzugriffe umfasst. Sicherungsdateien bleiben im persistenten Docker-Volume, bis sie administrativ entfernt werden.

Vereinslogos können als PNG/JPG bis 5 MB und 16 Megapixel hochgeladen werden. Die Anwendung prüft das Bild und speichert eine normalisierte PNG-Version in der Datenbank. Starter-, Ergebnis- und Mannschaftslisten nutzen das Logo; dauerhafte Fahrzeugkarten bleiben ohne Logo. Das MSC-Standardlogo kann wiederhergestellt oder der Druck ohne Logo gewählt werden.
