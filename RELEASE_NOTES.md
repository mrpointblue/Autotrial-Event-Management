# Autotrial 1.0.0

Erste stabile Docker-Version für Nennung, Papierbordkarten und nachträgliche Auswertung.

- Fahrer und Fahrzeuge mit Zuordnungen, HCF und druckbaren ID-Karten.
- Veranstaltungen anlegen, bearbeiten, schließen und wieder öffnen.
- Konfigurierbare Klassen, Farben und Sektionszahlen; Hilfeseite mit Farbzuordnung.
- Nennung mit Fahrzeugauswahl, Check-in und Bordkarten als beidseitiger Sammeldruck.
- Fehlerkategorien mit/ohne HCF, Korrekturen, Klassenfortschritt und NiW-Prüfung.
- Wertungstabelle B, Mannschaftswertung, Starterlisten, Siegerehrung und ADAC-Auswertung.
- Einstellungen, Logo und Datenbanksicherung.

## Docker starten

`compose.release.yaml` herunterladen und im selben Verzeichnis ausführen:

```sh
docker compose -f compose.release.yaml up -d --wait
```

Danach http://localhost:8020 öffnen. Docker-Image für AMD64 und ARM64:
`ghcr.io/mrpointblue/autotrial-event-management:1.0.0`.

Daten bleiben im Volume `autotrial_autotrial-data` erhalten. Vor dem Update eine
Datenbanksicherung erstellen. Bestehende Datenbanken werden beim Start auf Schema 10
migriert. Für ein Zurücksetzen auf eine frühere Version wird eine passende Sicherung benötigt.
Die Anwendung ist für ein vertrauenswürdiges lokales Veranstaltungsnetz vorgesehen;
sie enthält keine Benutzeranmeldung. Die Stable-Kennzeichnung ist keine sportrechtliche Abnahme.
