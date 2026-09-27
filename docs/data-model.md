# Datenmodell v1

| Entität | Zweck und Bedingungen |
| --- | --- |
| Driver | Person, feste positive eindeutige Startnummer, Kontakt, Club, ADAC-Nr. |
| Vehicle | Geteiltes Fahrzeug: Hersteller, Typ, Baujahr, Kennzeichen, Reifen, Maße in cm, Sperren, Aufbau, Fahrhilfen, Klasse, HCF und Vermerk |
| DriverVehicle | n:m-Verknüpfung. Zusammengesetzter Primärschlüssel; partieller Unique-Index erlaubt höchstens ein Standardfahrzeug je Fahrer. |
| Event | Datum, Ort, Veranstalter, Sektionen, Durchläufe, Reglementversion |
| Entry | Genau ein Start je Fahrer/Event; zusätzliche eindeutige Event-Startnummer. Kopie von Name, Startnummer, gesamten Fahrzeugdaten, Klasse, HCF. Beifahrer separat, kein Exklusivitätszwang. |
| SectionResult | Ein Wert je Nennung und ordinaler Sektion/Durchlauf. Decimal-Endwert oder NULL, zusätzlich gefahren/nicht gefahren. |

Startnummern werden im Grundgerüst nicht umnummeriert. Fahrzeugänderungen per API
ändern nur Stammdaten und zukünftige Nennungen. Historische Drucke und Ranglisten
verwenden ausschließlich den Entry-Snapshot. Es gibt bewusst keinen allgemeinen
Entry-Patch, der Fahrzeug-Snapshots stillschweigend überschreibt.

Nennung und technische Abnahme werden derzeit gemeinsam angelegt oder die
Abnahmeflags anschließend bestätigt. Ein falsches bereits genanntes Fahrzeug
benötigt künftig einen expliziten protokollierten Korrekturprozess.

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
Ränge werden nach exakten gespeicherten Summen bestimmt: 1, 1, 3.

Entry-Versionen verhindern das stille Überschreiben veralteter Eingabemasken.
Unique-Constraints und Transaktionen sichern Nennungen und Standardzuordnungen.
Fremdschlüssel sind aktiv. Schema-Version: SQLite `user_version = 1`.
