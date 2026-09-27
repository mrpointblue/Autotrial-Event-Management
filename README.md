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
6. Nach dem Event Startnummer eingeben und **bereits berechnete Sektions-Endwerte**
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
Diese Version übernimmt Endwerte inkl. HCF; sie dividiert Summen niemals erneut.
Falls die vorhandenen Papierkarten nur Rohwerte enthalten, muss vor dem echten
Einsatz die Eingabe um HCF-relevante und feste Punkte ergänzt werden.

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
Datenbankschema v1 wird beim ersten Start initialisiert. Noch keine Migrationen
für spätere Versionen; vor Schemaänderungen gesicherte Migrationen ergänzen.

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
