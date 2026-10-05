# Home Assistant

Die Integration `custom_components/opencook` zeigt den Live-Zustand des Kochroboters in Home
Assistant an. Sie fragt nur den OpenCook-Core ab (`docker compose up -d`, Port 8080), nie das Gerät.

## Installation

**HACS:** HACS → ⋮ → Benutzerdefinierte Repositories → `https://github.com/nikor30/cookingrobots`,
Typ „Integration“ → OpenCook installieren → HA neu starten.

**Manuell:** den Ordner `custom_components/opencook` nach `<HA-Konfiguration>/custom_components/`
kopieren und HA neu starten.

Danach: Einstellungen → Geräte & Dienste → Integration hinzufügen → **OpenCook** → Host
(z. B. `192.168.10.232`) und Port `8080`.

## Entitäten

| Entität | Typ | Inhalt |
| --- | --- | --- |
| Status | Sensor (Enum) | Bereit, Kocht, Pausiert, Schläft, Fehler, Fertig, Nicht erreichbar |
| Restzeit | Sensor (Dauer) | Restzeit des laufenden Schritts |
| Fertig um | Sensor (Zeitstempel) | Restzeit + Zeitpunkt der letzten Abfrage; nur während Kochen/Pause |
| Rezept | Sensor | Rezepttitel bzw. `Handbuch` für manuelle Läufe |
| Läuft | Binärsensor | an bei Kochen oder Pause |
| Rezept-ID, Modus, Fehlercode, Online | Diagnose | |

„Nicht erreichbar“ heißt: Das Gerät ist im Standby aus dem WLAN gegangen. Die Entitäten werden nur
dann „nicht verfügbar“, wenn der OpenCook-Core selbst nicht antwortet.

## Beispiel-Automation

```yaml
automation:
  - alias: Kochroboter fertig
    triggers:
      - trigger: state
        entity_id: sensor.cooking_robot_status
        to: complete
    actions:
      - action: notify.notify
        data:
          message: "{{ states('sensor.cooking_robot_recipe') }} ist fertig."
```
