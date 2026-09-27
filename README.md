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
4. Nennung: tatsächlich verwendetes Fahrzeug auswählen. Name, Startnummer,
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

Der HCF wird durch die technische Abnahme manuell bestätigt. Eine automatische
Berechnung einschließlich Rundung, SbS-Zuordnung und Q2-Grenzen ist noch nicht
freigegeben. Die Reglementformeln sind in `docs/rules-2026.md` dokumentiert.
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

Original-Bordkartenlayout und Punkteformat abstimmen; Snapshot-Korrekturen nur
mit Änderungsprotokoll; vollständige Stammdatenbearbeitung; HCF-Rechner nach
fachlicher Freigabe; Anmeldung/Rollen und Sicherungsoberfläche; signierte Releases
und Images für amd64/arm64. Automatische Updates und GHCR-Publishing sind noch
nicht eingerichtet.
