# CLAUDE.md – OpenCook

Projekt-Memory für Claude-Sessions. Kurz halten, bei jeder Erkenntnis aktualisieren.

## Projekt
Lokale Steuerung des Xiaomi Smart Cooking Robot EU (`chunmi.mfcp.c3os`) per Docker:
FastAPI-Core + React-Web-GUI + Home Assistant (MQTT Discovery) + Rezept-Konverter.
Fahrplan & Phasen: **KICKSTART.md**. Protokollwissen: **docs/protocol/xiaomi-c3os.md**.

## Status
- Aktuelle Phase: 0 (Setup)
- Offene Kernfragen: Q1 recipe-command-Format, Q3 Rückwärtslauf per API, Q4 Speed-Mapping, Q7 Live-Gewicht
  (Details KICKSTART.md §1)

## Harte Regeln
- Niemals Tokens, `ssecurity`, Cloud-Credentials, Pcaps, APKs, JS-Bundles, Firmware oder Xiaomi/Cookidoo-Inhalte
  (Texte, Bilder, Videos) committen. Alles davon → `research/private/` (gitignored).
- Keinen Code aus dem Mi-Home-Plugin übernehmen – nur Verhalten/Format dokumentieren (Clean-Room).
- Safety-Clamps im Treiber sind Pflicht und werden nicht durch Rezeptdaten überschrieben:
  manuell max. 150 °C, Speed-Cap über 80 °C, Präsenzbestätigung vor Heiz-/Messerschritten.
- Kein Test gegen das echte Gerät, bevor er gegen den Simulator grün ist.
- ORF (`schemas/orf-v1.json`) ist der Vertrag. Konverter gehen immer Quelle → ORF → Ziel.

## Konventionen
- Python 3.12, FastAPI, Pydantic v2, SQLModel/SQLite, async; ruff + mypy --strict
- Frontend: React + TS + Vite + Tailwind + TanStack Query
- Tests: pytest / pytest-asyncio / Hypothesis; Playwright E2E gegen `docker compose --profile sim`
- Conventional Commits, kleine PRs, ADRs in `docs/adr/` für Architekturentscheidungen
- Code/Bezeichner Englisch, Doku Deutsch

## Befehle
```bash
docker compose --profile sim up        # alles mit Simulator
pytest -q core/tests                   # Backend-Tests
python tools/prop_logger.py            # Properties live mitloggen (ENV: OC_DEVICE_IP, OC_DEVICE_TOKEN)
```

## Erkenntnisse (laufend ergänzen, mit Datum)
- 2026-10-03: MIoT-Spec c3os: siid4 piid10/11/12 = Dauer/Temp/Speed (R/W), siid2 aiid4 start-recipe-cook(recipe-command string, Format unbekannt).
