# Fachliche Grundlage und Grenzen

Gelesene Originale aus dem referenzierten Gespräch:

- 2026_Reglement_Autotrial.pdf, Stand 09.03.2026, 13 Seiten.
- 2026_Nennformular_Trial_ausfüllbar.pdf, Stand 06.04.2026, 1 Seite.

Originaldateien wurden nicht verändert und werden nicht im Code-Repository verteilt.

| Quelle | Regel | Umsetzung v0.1 |
| --- | --- | --- |
| Reglement S. 1, §2 | Fahrer startet einmal, darf mehrfach Beifahrer sein | unique(event, driver); Beifahrertext ohne Exklusivität |
| S. 2–3, §3 | O1/O2/S1/S2/S3/V1/V2/P/J/Q1/Q2a/Q2b/SbS; Abnahme entscheidet | Klassenvalidierung, manuell bestätigter HCF |
| S. 8, §4 | Papierabnahme vor Ausgabe der Bordkarte | Druck benötigt bestätigte Papier- und technische Abnahme |
| S. 8, §5 | Papierkarte alleinige Wertungsgrundlage; Verlust/Nichtabgabe/Verspätung führen zum Ausschluss | missing bleibt offen bis begründete NiW-Entscheidung |
| S. 9–11, §6 | 8/20/40/40 HCF-relevant, andere Strafen unverändert | Eingabe fertiger Endwerte; keine pauschale HCF-Division |
| S. 10, §6.1 | mind. 70 % gefahren; sonst NiW | gefahren-Markierung und explizite NiW-Entscheidung |
| S. 11, §6.2 | kleinste Summe gewinnt; Gleichstand gleicher Rang, Folgeplatz frei | Decimal-Summe, Wettbewerbsrangfolge |
| Nennformular S. 1 | Person, Kontakt, Club, ADAC, Beifahrer, Technik, Klasse/HCF, bezahlt/Abnahme | Felder im Stamm bzw. Entry; Papierunterschriften werden geprüft |

## HCF-Formel für spätere automatische Berechnung

Basis = ((Länge − L)/100) + ((Breite − B)/100 × 2,6)
      + ((Radstand − R)/100 × 2,6) + 1

| Art | L | B | R | Korrekturen als Summe auf die Basis |
| --- | --- | --- | --- | --- |
| Geländewagen | 300 | 139 | 193 | geschlossen +10 %, je Achssperre −10 %, Fahrhilfen −20 % |
| ATV | 185 | 101 | 115 | je Achssperre −10 % |
| Quad | 166 | 106 | 110 | keine Zusatzkorrektur genannt |

Maße in ganzen cm. Keine eigenmächtige automatische SbS-Zuordnung oder
Rundungsfestlegung. Der fragliche Text „ausgenommen Klasse D?“ steht im Original,
obwohl D in der Klassentabelle nicht definiert ist. Fachlich klären.

Q-Minis Fun und Q-Minis stehen im Nennformular, fehlen aber im gelieferten
Reglement. Diese Klassen benötigen eine zusätzliche Grundlage.

## Abgrenzung

Keine digitale Erfassung im Gelände, Fehlerzähler, Zeitnahme, Monitorausgabe,
Pokal-/Helferwertung oder automatische Entscheidung über technische Zulassung.
900-Punkte-Sonderfälle und Sektionsabbruch werden auf Papier beurteilt; die
Software erfindet sie nicht aus den Summen. Drucklayout ist ein erster Entwurf,
nicht das amtliche Nennformular und noch keine bestätigte vorhandene Bordkarte.
