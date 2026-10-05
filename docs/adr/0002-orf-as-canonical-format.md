# ADR 0002: ORF als kanonisches Rezeptformat

- Status: akzeptiert
- Datum: 2026-10-05

## Kontext

Rezepte kommen aus mehreren Quellen (eigene Eingabe, Thermomix-Freitext, Monsieur Cuisine,
schema.org, ggf. Xiaomi-nativ) und sollen auf mehreren Zielen laufen (Runner + Treiber, ggf. native
Geräterezepte, Export). Direkte Konverter zwischen allen Formaten wären n × m Stück, und das
native Xiaomi-Format ist noch unbekannt (Q1).

## Entscheidung

Es gibt genau ein kanonisches Format, das **OpenCook Recipe Format (ORF)**, Version 1.
`schemas/orf-v1.json` ist der Vertrag für Treiber, Konverter, API und GUI.
Konverter gehen immer **Quelle → ORF → Ziel**, nie direkt Gerät → Gerät.

Eckpunkte von ORF:

- Maschinenschritte sind **geräteneutral** und in physikalischen Einheiten (`temp_c`, `duration_s`);
  Drehzahl als normierte Stufe `level/of` plus `direction`. Das Mapping auf Gerätewerte liegt im
  Treiber.
- Schritt-Typen: `machine`, `user`, `weigh`, `wait`. Zutaten haben IDs und werden in Texten
  referenziert.
- Das Schema wird aus den Pydantic-Modellen generiert und in CI gegen Fixtures validiert.

## Begründung

- n + m statt n × m Konverter; jeder Konverter ist isoliert testbar (Golden-Files).
- Der Runner (Phase 5) hängt nur von ORF ab und funktioniert unabhängig davon, ob Q1 gelöst wird.
- Safety-Clamps sitzen im Treiber und gelten damit für jede Quelle – Rezeptdaten können sie nicht
  überschreiben.

## Alternativen

- **Xiaomi-natives Format als Kanon**: unbekannt, gerätespezifisch, rechtlich heikler.
- **schema.org/Recipe**: kennt keine Maschinenparameter; nur als Importquelle geeignet.

## Konsequenzen

- Verlustbehaftete Abbildungen (z. B. Stufen-Skalen, Sonderprogramme) müssen Konverter als
  Konfidenz-Score und Liste unsicherer Felder ausweisen statt still zu runden.
- Schemaänderungen sind Vertragsänderungen: inkompatible Änderungen → `orf_version` erhöhen und
  Migration bereitstellen.
