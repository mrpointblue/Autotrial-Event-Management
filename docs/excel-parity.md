# Abgleich mit der Auswertungsmappe vom 27.09.2026

Die bereitgestellte XLSM wurde statisch gelesen. Es wurden keine Makros ausgeführt
und keine echten Teilnehmer-, Kontakt- oder Ergebnisdaten in das Repository übernommen.
44 anonymisierte Zahlenfälle prüfen die Berechnung gegen die gespeicherten Einzelwerte.

| Excel-Funktion | Umsetzung |
| --- | --- |
| Makro1: Klassenblätter erstellen | Veranstaltung mit Standardklassen; eigene Klassen und Sektionsgruppen ergänzen oder unbenutzte Klassen entfernen |
| Auswerten: Fehler summieren, HCF, Sortierung, Tabelle B, Drucktabelle | Automatische Auswertung aus gespeicherten Nennungen; Klassendruck, Sammeldruck und ADAC-Druck |
| Sammeln: Klassen in Gesamtübersicht kopieren | ADAC-Übersicht direkt aus aktuellen Klassenwertungen, mit Kontakt-/Vereinsdaten |
| Datensammeln: Ergebnisse in eigene Datei speichern | PDF über Druckdialog und ADAC-CSV für Tabellenprogramme |
| Startnummern: Starterübersicht nach Klassen | Druckbare Starterliste mit optionalen Sektionsgruppen, ohne feste Zeilenbegrenzung |
| Loeschen_der_Blätter: Vorbereitung einer neuen Veranstaltung | Neue Veranstaltung anlegen; Stammdaten wiederverwenden, bisherige Ergebnisse bleiben erhalten |
| Pokalformel C4 | Planung mit 30 %, kaufmännisch gerundet und mindestens einem Pokal je belegter Klasse; feste Anzahl für Sonderregeln einstellbar |
| Mannschaftsblatt (nur feste Werte in Excel) | Nennung über 3–5 Startnummern; die drei höchsten Klassenpunkte werden automatisch addiert |

## Berechnung und Eingabe

Weiterhin Rohpunkte Fehler1/Fehler2 je Sektion, zusätzlich die Fehleranzahlen:
Rückwärtsfahren 8, Kugel 20, Torstange 40, Fuß 40 (HCF-relevant);
Band, vorzeitiges Verlassen sowie ausgelassenes Tor/Fremdhilfe jeweils 80,
900-Punkte-Fälle jeweils 900 (unverändert).
Die Excel enthält keinen eigenen Fuß-Zähler; die Software berücksichtigt diese
Fehlerart entsprechend dem bereits zugrunde gelegten Reglement.

Die Eingabeart wird je Sektion gespeichert. Fehleranzahlen und Rohsummen können
nicht gleichzeitig für dieselbe Sektion übergeben werden. Fehler1 wird über alle
Sektionen summiert und einmal durch den Nennungs-HCF geteilt; Fehler2 wird addiert.
Das Endergebnis wird gemäß Nutzervorgabe auf zwei Nachkommastellen gerundet.
Alle 44 gespeicherten Einzelberechnungen der Arbeitsmappe stimmen auf dieser
Genauigkeit überein. Gleichstände erhalten denselben Platz, Folgeränge bleiben frei.
NiW zählt zu N für Tabelle B, bekommt aber keine Punkte.

## Vermeidung veralteter Ergebnisse

Die gespeicherte Gesamtübersicht der Arbeitsmappe weicht bei 31 von 44
Startnummern in Klasse/Platz/Punkten von den aktuellen Klassen-Eingabebereichen ab.
Das Makro Sammeln muss dort separat aufgerufen werden. In der Software lesen
Übersicht, Druck und CSV dieselben aktuellen Ergebnisdaten.
Die PDF-Vorlage 2025 bleibt das Vorbild für die Gestaltung.

## Mannschaften

Drei bis fünf unterschiedliche genannte Startnummern pro Mannschaft.
Die besten drei Klassenpunktzahlen zählen; NiW trägt keine Punkte bei.
Bei Punktgleichheit ist die Startnummer nur für die nachvollziehbare Auswahl
unter gleichwertigen Mannschaftsmitgliedern entscheidend, nicht für Teamplätze.
Teams mit derselben Summe teilen den Platz. Nachfolgende Plätze bleiben frei.
Die endgültige Mannschaftsrangfolge erscheint erst, wenn die relevanten Klassen
aller Mannschaften vollständig sind. Änderungen an Nennung, Fehlern, HCF oder
Mannschaftsbesetzung fließen unmittelbar ein.

## Bewusste Unterschiede und Grenzen

Die Excel enthält keine automatische Mannschaftsberechnung. Diese wurde nach der
expliziten Vorgabe „fünf Fahrer, beste drei nach Punkten“ ergänzt.
Die Pokalformel prüft auf Klasse J, das vorhandene Jugendblatt heißt jedoch Jugend.
Eine Sonder-Pokalzahl wird daher bewusst über die Klasseneinstellung festgelegt.
Sektionsgruppen sind frei beschreibbar; keine festen Streckenbereiche aus 2026
werden als Vorgabe für zukünftige Veranstaltungen angenommen.
Freie Klassen sind Veranstaltungsentscheidungen, keine automatische Bestätigung
reglementkonformer Fahrzeugzuordnung.

ADAC-Kontaktdaten werden bei neuen Nennungen mitgespeichert. Bei alten Nennungen
werden aktuelle Stammdaten verwendet und als solche im ADAC-Druck/CSV bezeichnet.
Die öffentliche Ergebnisliste enthält keine Anschriften, E-Mails oder ADAC-Nummern.
Es wurde keine echte Veranstaltung aus der Arbeitsmappe automatisch importiert.
