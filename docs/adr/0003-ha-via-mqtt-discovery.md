# ADR 0003: Home-Assistant-Anbindung über MQTT Discovery

- Status: akzeptiert
- Datum: 2026-10-05

## Kontext

Home Assistant soll Status, Restzeit, Temperatur, Drehzahl und Gewicht anzeigen, Rezepte starten
bzw. pausieren können und bei „Schritt fertig“ Automationen auslösen (Push, Sprachansage).

## Entscheidung

Der Core veröffentlicht seine Entitäten per **MQTT Discovery**
(`homeassistant/<component>/opencook_<device>/<object>/config`) und nimmt Befehle über
Command-Topics entgegen. Der MQTT-Teil ist optional: ohne Broker-Konfiguration läuft der Core
unverändert. Eine HACS-Custom-Integration direkt gegen REST/WS bleibt eine spätere Option.

## Begründung

- Kein HA-seitiger Code, kein eigener Release-Zyklus gegen HA-Versionen; sofort nutzbar.
- MQTT ist in den meisten HA-Installationen bereits vorhanden und auch für Node-RED & Co. offen.
- `event`-Entitäten und MQTT-Trigger decken die Benachrichtigungsfälle ab.

## Alternativen

- **Custom Integration (HACS)**: bessere UX (Config Flow, kein Broker), aber deutlich mehr
  Pflegeaufwand – erst sinnvoll, wenn die API stabil ist.
- **Nur REST-Sensoren in HA**: Polling, keine Events, manuelle YAML-Konfiguration.

## Konsequenzen

- Zusätzliche Abhängigkeit auf einen Broker (optional `mosquitto` im Compose-File).
- **Sicherheit:** Start-Befehle aus HA umgehen das Präsenz-Gate nicht. „Präsenz bestätigt“ ist ein
  eigener, sich selbst zurücksetzender Switch; die Prüfung und alle Safety-Clamps bleiben im
  Core/Treiber.
- Broker-Zugangsdaten sind Secrets (ENV / Docker secrets), nie im Repo.
