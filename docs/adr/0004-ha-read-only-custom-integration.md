# ADR 0004: Read-only Home-Assistant-Integration als Custom Component

- Status: akzeptiert
- Datum: 2026-10-05
- Ergänzt: ADR 0003

## Kontext

ADR 0003 sieht MQTT Discovery als ersten HA-Weg vor und die Custom Integration erst später.
Inzwischen ist klar, dass das Gerät lokal nur gelesen werden kann (Experiment E6): Befehle,
Präsenz-Switch und Schritt-Events aus ADR 0003 gibt es vorerst nicht. Gewünscht sind jetzt nur die
Live-Daten in HA, und es ist offen, ob ein MQTT-Broker läuft.

## Entscheidung

Eine schlanke **Custom Integration** `custom_components/opencook` pollt alle 2 s die Read-only-API
des Cores (`GET /api/state`) und legt Sensoren an. Kein Broker, kein Gerätezugriff aus HA heraus:
Nur der Core spricht mit dem Gerät. Installation per HACS (Custom Repository) oder durch Kopieren.

## Konsequenzen

- Es gibt genau einen miIO-Client (den Core). Zwei Clients mit demselben Token stören sich
  gegenseitig (python-miio-Fehler beim parallelen Polling, siehe CLAUDE.md).
- MQTT Discovery aus ADR 0003 bleibt der Weg für Befehle und Events, sobald es welche gibt.
- `mypy --strict` deckt `custom_components/` nicht ab, weil Home Assistant nicht in der
  Dev-Umgebung installiert ist; geprüft wird per ruff und End-to-End-Test gegen einen HA-Container.
