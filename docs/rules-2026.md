# Fachliche Grundlage und Grenzen

Gelesene Originale aus dem referenzierten Gespräch:

- 2026_Reglement_Autotrial.pdf, Stand 09.03.2026, 13 Seiten.
- 2026_Nennformular_Trial_ausfüllbar.pdf, Stand 06.04.2026, 1 Seite.

Originaldateien wurden nicht verändert und werden nicht im Code-Repository verteilt.

| Quelle | Regel | Umsetzung v0.1 |
| --- | --- | --- |
| Reglement S. 1, §2 | Fahrer startet einmal, darf mehrfach Beifahrer sein | unique(event, driver); Beifahrertext ohne Exklusivität |
| S. 2–3, §3 | O1/O2/S1/S2/S3/V1/V2/P/J/Q1/Q2a/Q2b/SbS; Abnahme entscheidet | Klassenvalidierung, automatischer HCF-Vorschlag mit begründeter manueller Korrektur |
| S. 8, §4 | Papierabnahme vor Ausgabe der Bordkarte | Druck benötigt bestätigte Papier- und technische Abnahme |
| S. 8, §5 | Papierkarte alleinige Wertungsgrundlage; Verlust/Nichtabgabe/Verspätung führen zum Ausschluss | missing bleibt offen bis begründete NiW-Entscheidung |
| S. 9–11, §6 | 8/20/40/40 HCF-relevant, andere Strafen unverändert | Fehler1 als HCF-relevante Rohpunkte, Fehler2 unverändert; Summe Fehler1 / HCF + Summe Fehler2 |
| S. 10, §6.1 | mind. 70 % gefahren; sonst NiW | gefahren-Markierung und explizite NiW-Entscheidung |
| S. 11, §6.2 | kleinste Summe gewinnt; Gleichstand gleicher Rang, Folgeplatz frei | Decimal-Summe, Wettbewerbsrangfolge |
| Nennformular S. 1 | Person, Kontakt, Club, ADAC, Beifahrer, Technik, Klasse/HCF, bezahlt/Abnahme | Felder im Stamm bzw. Entry; Papierunterschriften werden geprüft |

## Implementierte HCF-Berechnung

Basis = ((Länge − L)/100) + ((Breite − B)/100 × 2,6)
      + ((Radstand − R)/100 × 2,6) + 1

| Art | L | B | R | Korrekturen als Summe auf die Basis |
| --- | --- | --- | --- | --- |
| Geländewagen | 300 | 139 | 193 | geschlossen +10 %, je Achssperre −10 %, Fahrhilfen −20 % |
| ATV | 185 | 101 | 115 | je Achssperre −10 % |
| Quad | 166 | 106 | 110 | keine Zusatzkorrektur genannt |

Maße in ganzen cm. Keine automatische SbS-Zuordnung. Die Rundung wurde vom Nutzer festgelegt:
kaufmännisch auf zwei Nachkommastellen nach Anwendung aller Korrekturen. Der fragliche Text „ausgenommen Klasse D?“ steht im Original,
obwohl D in der Klassentabelle nicht definiert ist. Fachlich klären.

Q-Minis Fun und Q-Minis stehen im Nennformular, fehlen aber im gelieferten
Reglement. Diese Klassen benötigen eine zusätzliche Grundlage.

## Abgrenzung

Keine digitale Erfassung im Gelände, Fehlerzähler, Zeitnahme, Monitorausgabe,
Pokal-/Helferwertung oder automatische Entscheidung über technische Zulassung.
900-Punkte-Sonderfälle und Sektionsabbruch werden auf Papier beurteilt; die
Software erfindet sie nicht aus den Summen. Drucklayout ist ein erster Entwurf,
nicht das amtliche Nennformular und noch keine bestätigte vorhandene Bordkarte.

Die automatische Berechnung verwendet Decimal und rundet den endgültigen HCF
kaufmännisch auf zwei Nachkommastellen (Nutzervorgabe). Zwischenwerte bleiben
für die Berechnung ungerundet. Die
Summe der Prozentkorrekturen wird einmal auf die Basis angewandt. Beispiel:
343/146/203 cm ergibt Basis 1,872; eine Sperre ergibt 1,6848 und damit den gespeicherten HCF 1,68. Automatische
API-Speicherung benötigt alle Maße. `hcf_mode=manual` benötigt HCF und Begründung.
Der verwendete Rechenweg bzw. die Begründung wird im HCF-Vermerk gespeichert
und mit dem Fahrzeug in neue Nennungen übernommen. Alte Snapshots bleiben gleich.

## Wertungstabelle B

Zusätzliche Grundlage: `ADAC Motorsport Schleswig-Holstein | Wertungstabelle B.pdf`,
vom Nutzer bereitgestellter Web-Ausdruck vom 27.09.2026, zwei Seiten.
Quelle: https://motorsport.adac-sh.de/meisterschaften/tabelle-c/wertungstabelle-b

Formel: Punkte = (80 − (Platz × 30) / (N + 1)) × 10.
Die Software verwendet die Formel auch für größere Teilnehmerfelder als die im
Ausdruck sichtbaren Spalten. Die Tabelle zeigt ganze Punkte; kaufmännische
Rundung entspricht den Referenzwerten (z. B. N=7, Platz 5: 612,5 → 613).

N ist die Anzahl der Nennungen in der jeweiligen Klasse, einschließlich NiW
(vom Nutzer ausdrücklich bestätigt). NiW erhält keine Wertungspunkte und wird
mit einem Strich angezeigt. Gleichstände übernehmen denselben Platz und dieselben
Wertungspunkte; nachfolgende Plätze bleiben gemäß Trial-Reglement frei.

Beispiel mit vier Teilnehmern, davon einer NiW: Plätze 1, 1, 3, NiW ergeben
740, 740, 620, keine Punkte. Eine Klasse wird erst nach vollständiger Bearbeitung
angezeigt und zum Ergebnisdruck freigegeben. Klassenwechsel verändern N und
damit die Punkte in den betroffenen Klassen; die Berechnung erfolgt immer aus
dem aktuellen Nennungs-/Wertungsstand, ohne gespeicherte Punktkopien.
