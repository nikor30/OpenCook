# ADR 0001: Python als Backend-Sprache

- Status: akzeptiert
- Datum: 2026-10-05

## Kontext

Der Core spricht das Gerät per miIO (UDP 54321, Token-verschlüsselt) an, führt Rezepte als
State-Machine aus und stellt REST/WebSocket für Web-GUI und Home Assistant bereit. Für das
Reverse Engineering (Phase 1–2) brauchen wir außerdem Werkzeuge zum Mitloggen von Properties und
zum Entschlüsseln von miIO-Pcaps.

## Entscheidung

Backend in **Python 3.12** mit FastAPI, Pydantic v2 und SQLModel/SQLite, durchgehend async.
Gerätezugriff über `python-miio` (MIoT generic) hinter einem eigenen async Wrapper; blockierende
Aufrufe laufen im Executor. Qualität: ruff, `mypy --strict`, pytest/pytest-asyncio/Hypothesis.

## Begründung

- Das miIO-Ökosystem (python-miio, micloud, Token-Extractor, hass-xiaomi-miot) ist Python –
  Protokoll, Handshake und Pcap-Parser müssen nicht neu geschrieben werden.
- RE-Skripte in `tools/` und Produktivcode teilen sich Sprache und Bibliotheken.
- FastAPI liefert OpenAPI und WebSockets ohne Zusatzaufwand; Pydantic-Modelle erzeugen das
  ORF-JSON-Schema (siehe ADR 0002).

## Alternativen

- **TypeScript/Node** (eine Sprache mit dem Frontend): miIO-Bibliotheken sind dort schlechter
  gepflegt, MIoT-Unterstützung lückenhaft.
- **Go/Rust**: kleine Images, aber miIO müsste selbst implementiert werden – falscher Fokus.

## Konsequenzen

- `python-miio` ist synchron und wenig aktiv gepflegt; `genericmiot` gibt es nur auf dem
  master-Stand. Der Wrapper kapselt die Bibliothek, damit sie austauschbar bleibt.
- Zwei Toolchains im Repo (Python + Node fürs Frontend); Devcontainer und CI decken beide ab.
