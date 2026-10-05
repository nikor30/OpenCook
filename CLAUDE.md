# CLAUDE.md – OpenCook

Projekt-Memory für Claude-Sessions. Kurz halten, bei jeder Erkenntnis aktualisieren.

## Projekt
Lokale Steuerung des Xiaomi Smart Cooking Robot EU (`chunmi.mfcp.c3os`) per Docker:
FastAPI-Core + React-Web-GUI + Home Assistant (MQTT Discovery) + Rezept-Konverter.
Fahrplan & Phasen: **KICKSTART.md**. Protokollwissen: **docs/protocol/xiaomi-c3os.md**.

## Status
- Aktuelle Phase: 1 (Recon) – Phase 0 (Setup) erledigt 2026-10-05
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
pip install -e "core[dev]"             # Dev-Umgebung (im Devcontainer automatisch)
pytest -q core/tests                   # Backend-Tests
pre-commit run --all-files             # ruff, mypy --strict, prettier, gitleaks
python tools/prop_logger.py            # Properties live mitloggen (ENV: OC_DEVICE_IP, OC_DEVICE_TOKEN)
```

## Erkenntnisse (laufend ergänzen, mit Datum)
- 2026-10-03: MIoT-Spec c3os: siid4 piid10/11/12 = Dauer/Temp/Speed (R/W), siid2 aiid4 start-recipe-cook(recipe-command string, Format unbekannt).
- 2026-10-05: gitleaks-Defaultregeln erkennen nackte miIO-Tokens (32 Hex) nicht → eigene Regeln in `.gitleaks.toml`.
  Der pre-commit-Hook scannt nur Staged-Änderungen; die komplette Historie prüft der CI-Job `secrets`.
- 2026-10-05: `miiocli genericmiot` gibt es nur auf python-miio master (0.6 dev), nicht in 0.5.x → Pin in
  `.devcontainer/post-create.sh`.
- 2026-10-05: Gerät hat keinen offenen TCP-Port (kein ADB/HTTP); nur miIO UDP 54321. Hello-Antwort liefert keinen
  brauchbaren Token → Token per Cloud-Extractor nötig. IP + Token stehen in `.env` (nicht im Repo).
- 2026-10-05: Lokaler Lesezugriff läuft. `get_properties` braucht die echte Device-ID als `did`, sonst `-4007`.
  Gerät ist Android-basiert (fw 1.0_179) und verschwindet im Standby aus dem WLAN → vor Tests aufwecken.
- 2026-10-05: Keine Portscans mehr gegen das Gerät (bringt nichts, alle TCP-Ports zu).
- 2026-10-05: E1–E3: Display-Läufe zeigen nur status/remaining-time (4.14); Temp/Speed/Dauer, Drehrichtung und
  Gewicht sind NICHT lesbar. Q3/Q4/Q7 nur noch über Setzen per API (E6) klärbar. Aktionen siid 4 aiid 1–8 siehe
  docs/protocol. Notizen: research/notes/experiments.md.
- 2026-10-05: E4: offizielles Rezept → cook-id numerisch, cook-type 4, cook-name = Titel; recipe-command bleibt
  leer. Q1 ist durch Mitlesen am Gerät nicht lösbar → Plugin-Analyse (Phase 2a) oder Raten mit cook-id (E6).
- 2026-10-05: E6: set_properties und alle Aktionen (inkl. start-cook) antworten code 0, bewirken aber NICHTS am
  Gerät. Lokale Steuerung über die Spec-Aktionen ist damit vorerst nicht belegt → Phase 2a/2b (Plugin, App↔Cloud)
  muss zeigen, welche Befehle die App wirklich schickt.

