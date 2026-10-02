# Datenmodell v4

| Entität | Zweck und Bedingungen |
| --- | --- |
| Driver | Person, feste positive eindeutige Startnummer, Kontakt, Club, ADAC-Nr. |
| Vehicle | Geteiltes Fahrzeug: Hersteller, Typ, Baujahr, Kennzeichen, Reifen, Maße in cm, Sperren, Aufbau, Fahrhilfen, Klasse, HCF und Vermerk |
| DriverVehicle | n:m-Verknüpfung. Zusammengesetzter Primärschlüssel; partieller Unique-Index erlaubt höchstens ein Standardfahrzeug je Fahrer. |
| Event | Datum, Ort, Veranstalter, Sektionen, Durchläufe, Reglementversion |
| Entry | Genau ein Start je Fahrer/Event; zusätzliche eindeutige Event-Startnummer. Kopie von Name, Startnummer, gesamten Fahrzeugdaten, Klasse, HCF. Beifahrer separat, kein Exklusivitätszwang. |
| SectionResult | Je Sektion/Durchlauf Fehler1 und Fehler2 als optionale Rohpunkte, berechneter Endwert oder alter Endwert; zusätzlich gefahren/nicht gefahren. |

Startnummern werden im Grundgerüst nicht umnummeriert. Fahrzeugänderungen per API
ändern nur Stammdaten und zukünftige Nennungen. Historische Drucke und Ranglisten
verwenden ausschließlich den Entry-Snapshot. Explizite Nennungskorrekturen sind über die Bearbeitungsseite und einen validierten
API-Endpunkt möglich. Versionen verhindern das Überschreiben veralteter Formulare.
Der Fahrer und die Startnummer können über diesen Endpunkt nicht ersetzt werden.
Bei gleichem Fahrzeug bleibt der historische technische Snapshot bestehen; bei
bewusstem Fahrzeugwechsel wird eine neue Kopie des zugeordneten Fahrzeugs erzeugt.
Veranstaltungsklasse und HCF werden im Entry und seinem Snapshot konsistent geändert.

`EntryChange` speichert UTC-Zeit, Änderungsgrund sowie Vorher-/Nachher-Werte für
explizite Nennungskorrekturen. Die zusätzliche Tabelle wird beim Start angelegt;
bestehende Tabellen und Nennungen werden nicht migriert oder überschrieben.
Die Anmeldung wird zentral verwaltet; ältere Änderungsprotokolle bleiben unverändert.

## Zwei unabhängige Zustände

- `card_status`: `missing`, `received`
- `scoring_status`: `pending`, `complete`, `niw`

NiW ist eine begründete Entscheidung, kein Synonym für eine noch fehlende Karte.
Eine endgültig nicht abgegebene Karte kann deshalb `missing + niw` sein.
`complete` erfordert alle vorgesehenen Endwerte, auch gültige Nullen.
NiW benötigt eine nichtleere Begründung und kann ohne Sektionswerte vorliegen.
Eine Klasse ist druckbereit, wenn alle ihre Nennungen complete oder niw sind.
Ohne Nennungen wird keine druckbare Klasse angeboten.

70-%-Prüfung erfolgt auf tatsächlich gefahrenen Sektionen/Durchläufen, nicht auf
einem Punktwert. 900 Punkte allein beweisen keine Nichtbefahrung. Unter 70 % wird
der Abschluss ohne explizite NiW-Begründung abgewiesen.

Werte verwenden Decimal/Numeric (4 Nachkommastellen für Endwerte, 6 für HCF).
Das ist die Speicherpräzision. HCF-Werte werden vor dem Speichern und für neue
Nennungen kaufmännisch auf zwei Nachkommastellen gerundet (Nutzervorgabe).
Historische Snapshots bleiben unverändert.
Ränge werden nach der auf zwei Nachkommastellen gerundeten Gesamtsumme bestimmt: 1, 1, 3.

Entry-Versionen verhindern das stille Überschreiben veralteter Eingabemasken.
Unique-Constraints und Transaktionen sichern Nennungen und Standardzuordnungen.
Fremdschlüssel sind aktiv. Aktuelle Schema-Version: SQLite `user_version = 12`.

Fehler1 wird aus allen getrennt erfassten Sektionen summiert und einmal durch den
HCF des Entry-Snapshots geteilt. Fehler2 und etwaige alte Endwerte werden addiert.
Erst das Gesamtergebnis wird kaufmännisch auf zwei Nachkommastellen gerundet.
Der je Sektion zwischengespeicherte Endwert (vier Nachkommastellen) ist bei
getrennten Fehlern nicht die Grundlage der Gesamtsumme, um Rundungsdrift zu vermeiden.
Beide Rohfelder sind für eine vollständige Sektion erforderlich.

Die Migration ergänzt error1/error2 als NULL bei Altdaten und erhält points.
Eine Mischung aus alten und neuen Sektionen ist möglich; getrennte Fehlersummen
werden erst angezeigt, wenn alle Sektionen aufgeteilt sind. Beim Ändern von HCF
oder Fahrzeug ist weiterhin eine erneute Bestätigung der Bordkarte erforderlich.

## Klassen, Kontaktdaten und Mannschaften

EventClass gehört zu einer Veranstaltung und enthält Code, Farbe, Sektionsanzahl und
optionale feste Pokalanzahl. Neue Veranstaltungen erhalten die Standardklassen.
Die Migration ergänzt bestehende Veranstaltungsklassen einschließlich genutzter
Klassenbezeichnungen. Belegte Klassen können nicht gelöscht werden.

Entry.driver_snapshot hält Kontakt-, Vereins- und ADAC-Daten zum Nennungszeitpunkt.
Bei älteren Nennungen bleibt dieser Snapshot NULL; Berichte kennzeichnen den
Rückgriff auf heutige Stammdaten. SectionResult.error_counts speichert bei
Anzahl-Eingabe die einzelnen Zähler als JSON und die daraus berechneten Rohpunkte.

Team gehört zur Veranstaltung. TeamMember verbindet 3–5 unterschiedliche
Event-Nennungen. Besetzungsänderungen sind versioniert. Punkte und Platz werden
aus aktuellen Klassenwertungen abgeleitet und nicht separat gespeichert.

## Bordkartensummen (Schema 5)

`Entry.card_summary` speichert alternativ zu den einzelnen SectionResult-Zeilen die Summen der gesamten Bordkarte: elf Fehleranzahlen, daraus abgeleitete Rohpunktsummen Fehler1/Fehler2 und Anzahl gefahrener Sektionsbefahrungen. Alternativ können die Rohpunktsummen direkt erfasst werden. Beide Speicherformen werden nie zugleich gewertet. Eine fehlende Anzahl gefahrener Befahrungen bleibt unvollständig; unter 70 % ist eine ausdrückliche NiW-Begründung nötig. Bestehende Sektionswerte werden beim Öffnen nicht verändert und erst nach bewusstem Speichern einer Summenerfassung ersetzt. Alte zusammengefasste Fehlerkategorien werden nicht automatisch in unbekannte Einzelkategorien zerlegt. Endwerte ohne Rohpunkte bleiben separat korrigierbar.

Kategorien nach Reglement §6.1: Rückwärtsfahren 8; Kugel 20; Torstange 40; Fuß 40; Tore umfahren 80; Fremdhilfe 80; Band zerreißen 80; Ende der Sektionsbefahrung 80; Nichtbefahren 900; Anschnallpflicht 900; Helmpflicht 900. Die ersten vier zählen zu Fehler1, alle anderen zu Fehler2. Sektionsbezogene Sonderfälle und die 900-Punkte-Grenze bei Abbruch müssen auf Papier geprüft werden; die reine Gesamtsumme enthält keine Information zur Verteilung auf Sektionen. Für solche Karten stehen geprüfte Rohpunktsummen zur Verfügung.

## Sektionsanzahl je Klasse und automatische NiW (Schema 6)

`EventClass.required_sections` ist die vorgeschriebene Gesamtzahl der Sektionsbefahrungen je Veranstaltungsklasse, Standard 5. Die Veranstaltungsanlage nimmt `class_sections` als Zuordnung von Klassenname zu Anzahl entgegen. Bestehende Klassen übernehmen bei der Migration die bisherige Veranstaltungszahl (Sektionen × Durchläufe). Änderungen sind unter Datenbank → Klassen möglich.

In der Summenerfassung wird gefahren = vorgeschrieben − Nichtbefahren berechnet. Nur die Kategorie Nichtbefahren zählt hierfür, nicht die beiden anderen 900-Punkte-Kategorien. Weniger als 70 % führt automatisch zu NiW; genau 70 % bleibt in Wertung. Automatische Gründe werden mit `card_summary.auto_niw` markiert und bei Korrekturen neu berechnet. Manuelle Ausschlussgründe bleiben erhalten. Klassenwechsel und Änderungen der vorgeschriebenen Anzahl berechnen Summenkarten neu und erhöhen die Version gegen veraltete Eingaben. Wenn die gespeicherte Anzahl Nichtbefahren die neue Vorgabe übersteigt, bleibt die Karte zur Korrektur offen. Alte Sektionskarten bleiben bei geänderter Vorgabe zur Prüfung offen.

Bei Rohpunktsummen gibt es eine separate Anzahl Nichtbefahren; die Strafpunkte selbst müssen bereits in Fehler2 enthalten sein. Das alte Feld gefahrene Sektionen ist aus dem Formular entfernt; ältere API-Clients werden weiterhin unterstützt. Bordkarten drucken die klassenspezifische Gesamtzahl, mit höchstens fünf Zeilen je Blatt.


## Veranstalter und Identität (Schema 12)

Das Identitätsverzeichnis `identity.sqlite3` enthält Veranstalter (UUID, Name,
Anschrift, Kontakt), Benutzer (scrypt-Passworthash, Rolle, Veranstalter-ID), gehashte
Sitzungstoken und Anmeldebegrenzung. Der Standard-Veranstalter verwendet die vorhandene
`autotrial.sqlite3`; weitere Veranstalter verwenden `organizers/<UUID>/autotrial.sqlite3`.
Alle Fachdaten einschließlich Einstellungen und Logo gehören strukturell zu genau
einem solchen Bereich. Es gibt keine mandantenübergreifenden Fremdschlüssel.

Ein ASGI-Middleware setzt den Bereich ausschließlich aus der geprüften Sitzung.
ContextVar-basierte Verbindungswahl gilt auch in FastAPI-Workerthreads und in allen
Services, Druck- und Sicherungsrouten. Ein nicht privilegierter Benutzer kann den
Bereich nicht über URL- oder Formulardaten wählen. Ressourcen-IDs gelten lokal; UUIDs
für Veranstaltungen, Fahrer, Fahrzeuge, Nennungen, Ergebnisse, Protokolle und Teams
sind die transportablen Identitäten.

`Event.organizer_id` speichert die Veranstalter-UUID zusätzlich zur strukturellen Trennung.
`Event.revision` und `updated_at` werden konservativ auch bei Änderungen an gemeinsam
verwendeten Stammdaten aktualisiert. Importierte Versionen bleiben erhalten.
`.trialdata` Format 1 ist begrenztes UTF-8-JSON (20 MB), kein SQL und kein Archiv.
Referenzen verwenden UUIDs und werden beim Import auf lokale IDs umgesetzt. Sämtliche
Fachdaten des Imports werden in einer Transaktion geschrieben. Versionskonflikte
werden nur diagnostiziert; eine Zusammenführung ist separat nachrüstbar.

Die gemeinsame Ausgangsversion wird unter `AppSetting.transfer:<Event-UUID>` als
SHA-256-Inhaltshash gespeichert. Der Hash erkennt Änderungen, ist jedoch keine
kryptografische Signatur und bestätigt nicht die Herkunft einer Datei.
