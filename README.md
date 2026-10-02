# Autotrial · Veranstalterverwaltung (Entwicklungsstand 1.1)

Eigenständiges Schwesterprojekt der Quad Parallel Race Software: Nennung,
Papierbordkarten und nachträgliche Auswertung mit getrennten Veranstaltern, Benutzerrollen und Veranstaltungstransport.

Die stabile Version 1.0.0 bleibt unverändert verfügbar. Die hier beschriebenen neuen Funktionen werden aus dem aktuellen Quellstand gebaut.

## Docker-only starten

Docker Engine / Docker Desktop mit Compose ist die einzige Laufzeitvoraussetzung.

Fertiges Image aus der GitHub Container Registry (AMD64 und ARM64):

```sh
docker compose -f compose.release.yaml up -d --wait
```

Die Datei `compose.release.yaml` ist auch als Download bei der GitHub-Version
`v1.0.0` verfügbar. Sie verwendet fest `ghcr.io/mrpointblue/autotrial-event-management:1.0.0`.
Alternativ direkt aus dem Repository bauen:

```sh
docker compose up -d --build --wait
```

Oberfläche: http://localhost:8020 · API-Dokumentation: http://localhost:8020/docs

Port 8020 vermeidet Konflikte mit Quad Race (8000/8010). Standardmäßig ist nur
lokaler Zugriff möglich. Für das vertrauenswürdige Veranstaltungsnetz `.env.example`
nach `.env` kopieren und `AUTOTRIAL_BIND=0.0.0.0` setzen. Benutzeranmeldung und Rollenverwaltung sind vorhanden. Für Zugriff außerhalb eines
vertrauenswürdigen lokalen Netzes HTTPS über einen Reverse Proxy verwenden.

Ein Container enthält FastAPI, Jinja-Oberfläche und SQLite. Veranstalterdaten sind in getrennten SQLite-Dateien gespeichert; Konten und Veranstalter-IDs liegen in einem zentralen Identitätsverzeichnis. Persistentes Volume
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
docker build -t autotrial:1.0.0 .
docker run --rm -v "$PWD/tests:/app/tests:ro" -v "$PWD/requirements-dev.txt:/app/requirements-dev.txt:ro" --user root autotrial:1.0.0 sh -c 'pip install -r requirements-dev.txt && python -m pytest -q'
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
Veranstaltungsklassen mit Farbe, Sektionsanzahl und Pokalplanung, Fehleranzahl-Eingabe,
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

Der Datenbankexport verwendet die SQLite-Backup-Schnittstelle und enthält auch Einstellungen und Logo. Der Import akzeptiert passende Exporte mit Schema 12 bis 100 MB. Vor dem Ersetzen wird unter `/app/data/backups` automatisch eine herunterladbare Sicherung angelegt. Ein fehlgeschlagener Import setzt die Datenbank aus dieser Sicherung zurück. Während eines Imports werden andere Anfragen zurückgestellt. **Die Anwendung muss mit einem Uvicorn-Worker betrieben werden**, wie in Dockerfile/Compose vorgegeben, damit die Importsperre alle Schreibzugriffe umfasst. Sicherungsdateien bleiben im persistenten Docker-Volume, bis sie administrativ entfernt werden.

Vereinslogos können als PNG/JPG bis 5 MB und 16 Megapixel hochgeladen werden. Die Anwendung prüft das Bild und speichert eine normalisierte PNG-Version in der Datenbank. Starter-, Ergebnis- und Mannschaftslisten nutzen das Logo; dauerhafte Fahrzeugkarten bleiben ohne Logo. Das MSC-Standardlogo kann wiederhergestellt oder der Druck ohne Logo gewählt werden.

## Alle Bordkarten und Richter-Rückseite

Unter **Nennung / Check-in → Genannte Fahrer → Alle Bordkarten drucken** entsteht
ein Sammeldruck in Startnummernreihenfolge. Voraussetzung: mindestens eine Nennung
und bestätigte Papier- sowie technische Abnahme für alle genannten Fahrer. Offene
Abnahmen werden angezeigt; der Sammeldruck lässt keine Fahrer stillschweigend aus.
Einzeldruck und Nachdruck bleiben verfügbar. Drucken verändert keine Nennungsdaten.

Die Bordkarten verwenden die Sektionszahl der jeweiligen Veranstaltungsklasse.
Auf jede Vorderseite mit bis zu zehn Sektionen folgt unmittelbar ihre Richter-Rückseite,
auch bei mehreren Blättern pro Fahrer. Im Druckdialog **A4 Querformat, beidseitig,
an kurzer Kante wenden** wählen. Die Anwendung kann den Duplexmodus des Druckers
nicht selbst einschalten. Vorder- und Rückseiten werden auf die bedruckbare Seite angepasst.

Die Richterhilfe fasst die für den Sektionsbetrieb relevanten Bestimmungen des
Reglements 2026 (Stand 09.03.2026) zusammen und verlinkt das Original. Sie enthält
Fehlerpunkte, Torregeln, Sicherheitsvorgaben, Abbruchgründe, die 900-Punkte-Abbruchgrenze
und den klassenabhängigen Mindestumfang für 70 %. Sonderbestimmungen der Veranstaltung
bleiben zu beachten. Die bereitgestellte MSC-Bordkarte 2025 präzisiert Fremdhilfe als Einweisen trotz Abmahnung.
Das Drucklayout folgt dieser Vorlage: Strichliste vorne, breite Fehlerdefinitionen hinten.
Alle elf Fehlerkategorien entsprechen der Eingabemaske, einschließlich drei getrennter
900-Punkte-Spalten. Reihenfolge, Namen und Punktwerte stammen für Druck und Erfassung
aus der gemeinsamen Definition in `backend/templates/penalties.html`. Es wird keine zusätzliche
Strafentscheidung aus der Druckfunktion abgeleitet.


## Neue Veranstalterverwaltung verwenden

Die neue Version zunächst aus dem Quellstand starten:

```sh
docker compose up -d --build --wait
```

Beim ersten Öffnen im Browser einen Benutzernamen und ein Passwort mit mindestens
zwölf Zeichen festlegen. Dieses erste Konto ist der Administrator. Danach ist die
Ersteinrichtung gesperrt; weitere Benutzer werden in der Benutzerverwaltung angelegt.
Es gibt keinen Einrichtungsschlüssel und kein Standardpasswort. Die Ersteinrichtung
am lokalen Rechner abschließen, bevor die Anwendung im Veranstaltungsnetz freigegeben wird.

Bestehende Daten und das bisherige Logo gehören nach der automatischen Umstellung
zum Standard-Veranstalter. Vor der Umstellung wird pro vorhandenem Datenbereich eine
Sicherung unter `backups/before-organizers-schema-*.sqlite3` angelegt.

Unter **Veranstalter / Benutzer** kann der Administrator Veranstalter anlegen und
wechseln. Veranstalter-Administratoren verwalten nur den eigenen Veranstalter und
dessen Benutzer. Bearbeiter können Veranstaltungen und Stammdaten bearbeiten;
Lesekonten können ansehen, drucken und exportieren. Rechte gelten serverseitig auch
bei direkten API-Aufrufen. Sitzungen laufen nach zwölf Stunden ab.

## Veranstaltungen transportieren

**Veranstaltung exportieren** liefert eine einzelne `.trialdata`-Datei. Beim Anlegen
wird **Sollen Daten importiert werden? → Ja** angeboten. Die Datei enthält eine
Veranstaltung mit Klassen, Nennungen, Ergebnissen, Änderungsverlauf und Mannschaften
sowie die Fahrer, Fahrzeuge und Zuordnungen des Veranstalters. Veranstalterprofil und
Logo sind enthalten, Benutzerkonten und Passwörter nicht. Persönliche Teilnehmerdaten
sind daher Bestandteil dieser Datei.

Auf dem Zielsystem muss derselbe Veranstalter mit derselben UUID ausgewählt sein.
Ein übergeordneter Administrator kann ihn unter Verwendung dieser ID anlegen.
Ein Import übernimmt keine fremde Veranstalteridentität und kann nicht in einen
anderen Veranstalterbereich schreiben. Profile und Logos werden nur durch
Administratoren und nur in noch leere Felder übernommen. Konten werden lokal verwaltet.

Gleiche Veranstaltungs-UUID und gleicher Inhalt: keine erneute Anlage. Abweichende
Stände: Konflikthinweis, kein Überschreiben. Startnummernkollisionen und widersprüchliche
Stammdaten führen zum vollständigen Abbruch ohne Teilimport. Automatisches Mischen
zweier bearbeiteter Stände ist ausdrücklich noch nicht implementiert.

Veranstaltungen tragen UUID, Änderungsstand und UTC-Änderungszeit. Ein Inhaltshash und
eine gemeinsame Ausgangsversion ermöglichen die Unterscheidung von identischen,
neuen, lokal geänderten und beidseitig geänderten Ständen. Unabhängige Änderungszähler
werden nicht allein als Beweis für einen neueren Stand verwendet.

## Vollständige Installationssicherung

Die Sicherungsfunktion in Einstellungen sichert den ausgewählten Veranstalter.
Für eine komplette Installationssicherung einschließlich Konten und aller Veranstalter
bei gestopptem Container das gesamte persistente Volume sichern. Es enthält
`identity.sqlite3`, den bisherigen Standard-Datenbereich und `organizers/<UUID>/`.
Die Einzeldatei `.trialdata` ist für den Veranstaltungstransport vorgesehen, nicht
als Ersatz für die Sicherung sämtlicher Benutzerkonten.
