# Protokoll `chunmi.mfcp.c3os` (Xiaomi Smart Cooking Robot EU)

**Version:** 0.1 – MIoT-Spec plus erster lokaler Lesezugriff (2026-10-05, Firmware `1.0_179`).
Clean-Room: hier steht nur beobachtetes Verhalten/Format, kein Code und keine Inhalte aus dem Mi-Home-Plugin.

Transport: miIO, UDP 54321, lokal mit Geräte-Token. Quelle der Spec: <https://home.miot-spec.com/spec/chunmi.mfcp.c3os>

## siid 2 – Multifunction Cooking Pot

| piid | Name           | Typ    | Zugriff | Werte                                                         |
| ---- | -------------- | ------ | ------- | ------------------------------------------------------------- |
| 1    | status         | uint8  | R/N     | 0 Standby, 1 Cooking, 3 Paused, 6 Sleep, 8 Error, 11 Complete |
| 2    | mode           | uint8  | R/W/N   | 0 Stop, 1 Stir-fry, 2 Steam, 3 Stew, 4 Warm, 5 Other          |
| 3    | left-time      | uint32 | R/N     | 0–999999                                                      |
| 4    | on             | bool   | R/W/N   |                                                               |
| 5    | fault          | uint16 | R/N     | 0–9999                                                        |
| 10   | recipe-command | string | R/W     | Format unbekannt (Q1)                                         |

Actions: `aiid 1` start-cook · `aiid 2` cancel · `aiid 3` pause · `aiid 4` start-recipe-cook (in: piid 10)
Event: `eiid 1` cooking-finished

## siid 3 – Alarm

| piid | Name   | Typ   | Werte |
| ---- | ------ | ----- | ----- |
| 1    | alarm  | bool  |       |
| 2    | volume | uint8 | 0–100 |

## siid 4 – Automatic Cooker

| piid | Name           | Typ    | Zugriff | Werte                                      |
| ---- | -------------- | ------ | ------- | ------------------------------------------ |
| 3    | cook-id        | uint32 | R/N     | 0–999999999                                |
| 4    | cook-type      | uint8  | R/N     | 0 Official, 1 Single, 2 Mutable, 4 Recipe  |
| 5    | cook-name      | string | R/N     |                                            |
| 6    | property-a     | uint8  | R/N     | 0–99, Bedeutung unbekannt                  |
| 7    | property-b     | uint16 | R/N     | 0–9999, Bedeutung unbekannt                |
| 8    | property-c     | bool   | R/N     | Parameter von set-/get-setting             |
| 9    | property-d     | float  | R/N     | 0–99999999, Bedeutung unbekannt            |
| 10   | cook-duration  | uint16 | R/W/N   | 0–14400 s                                  |
| 11   | cook-temp      | uint8  | R/W/N   | 0–180 °C                                   |
| 12   | cook-speed     | uint8  | R/W/N   | 0–100, Mapping zu 20 Display-Stufen offen (Q4) |
| 13   | weigh-activity | bool   | R/W/N   |                                            |
| 14   | remaining-time | uint32 | R/N     | 0–14400                                    |

| aiid | Name         | in      | out     |
| ---- | ------------ | ------- | ------- |
| 1    | set-setting  | piid 8  |         |
| 2    | get-setting  |         | piid 8  |
| 3    | switch-weigh | piid 13 |         |
| 4    | get-time     |         | piid 14 |
| 5    | set-duration | piid 10 |         |
| 6    | set-temp     | piid 11 |         |
| 7    | set-speed    | piid 12 |         |
| 8    | set-zero     |         |         |

`recipe-command` (siid 2 piid 10) hat in der Spec keine Access-Flags – es ist nur Parameter von
`start-recipe-cook`. Lesen liefert trotzdem einen (leeren) String.

## Netzwerk (beobachtet 2026-10-05, Gerät im Standby)

- Antwortet auf ICMP und auf den miIO-Hello (UDP 54321, 32-Byte-Antwort mit Device-ID und Stamp).
- Das Checksum-Feld der Hello-Antwort ist weder Null noch `ff…`, taugt aber **nicht** als Token:
  ein damit verschlüsseltes `miIO.info` bleibt unbeantwortet. Der Token muss aus der Cloud kommen.
- TCP 1–65535: alle Ports geschlossen (RST). Kein ADB (5555), kein HTTP, kein RTSP → Q8 für TCP
  beantwortet. UDP-Scan steht noch aus.

## Lokaler Zugriff (verifiziert 2026-10-05)

- `miIO.info` mit Cloud-Token funktioniert: `model chunmi.mfcp.c3os`, `fw_ver 1.0_179`,
  `hw_ver Android`, `miio_ver 0.0.9`, `miio_client_ver 4.3.2`. Das Gerät ist also Android-basiert.
- **`did` muss die echte Device-ID sein** (Dezimalstring aus dem Hello-Header). Mit beliebigem `did`
  antwortet jede Property mit `code -4007`; ohne `did` kommt eine leere Ergebnisliste.
- `get_properties` liefert alle Properties aus siid 2, 3 und 4 (piid 3–14). Legacy-`get_prop` liefert nichts.
- siid 1 (Device Information) piid 1–5 ist lesbar, aber leer bzw. `"0"`.
- Im Standby meldet das Gerät sich aus dem WLAN ab (kein Ping, kein Hello). Der Treiber muss
  „nicht erreichbar“ daher als normalen Zustand behandeln, nicht als Fehler.

Werte im Standby (Display an, nichts läuft):

| Property | Wert | | Property | Wert |
| --- | --- | --- | --- | --- |
| 2.1 status | 0 | | 4.6 reserved | 0 (int) |
| 2.2 mode | 0 | | 4.7 reserved | 0 (int) |
| 2.3 left-time | 0 | | 4.8 reserved | **true** (bool) |
| 2.4 on | false | | 4.9 reserved | 0 (int) |
| 2.5 fault | 0 | | 4.10 cook-duration | 0 |
| 2.10 recipe-command | `""` | | 4.11 cook-temp | 0 |
| 3.1 alarm | false | | 4.12 cook-speed | 0 |
| 3.2 volume | 0 | | 4.13 weigh-activity | false |
| 4.3 cook-id | 0 | | 4.14 remaining-time | 0 |
| 4.4 cook-type | 0 | | 4.5 cook-name | `""` |

## Beobachtetes Verhalten bei manuellem Kochen (2026-10-05)

Details in `research/notes/experiments.md`.

- Ein am Display gestarteter manueller Lauf setzt `mode` 5, `cook-name` `Handbuch`, `cook-id` 1 und
  zählt `remaining-time` (4.14) sekündlich herunter. `left-time` (2.3) bleibt 0.
- Statusfolge: 0 → 1 → (3 bei Pause → 1) → 11 → nach rund 14 s wieder 0.
- `cook-duration`, `cook-temp`, `cook-speed` bleiben dabei 0: sie spiegeln **nicht** die am Display
  eingestellten Werte.
- Drehrichtung und Gewicht erscheinen in keiner Property; die am Display aktivierte Waage ändert
  `weigh-activity` nicht.

## Beobachtetes Verhalten bei Rezepten (2026-10-05)

- Ein am Display gestartetes offizielles Rezept setzt `cook-id` auf eine numerische Rezept-ID,
  `cook-type` 4 und `cook-name` auf den Rezepttitel; `mode` ist auch hier 5.
- `remaining-time` läuft ab der Dauer des Maschinenschritts herunter. Abbruch setzt `status` und `mode`
  auf 0; `cook-id`, `cook-type` und `cook-name` bleiben stehen.
- `recipe-command` bleibt leer. Der Parameter wird nur als Eingabe von `start-recipe-cook` verwendet,
  nie vom Gerät zurückgemeldet.

## Schreibzugriffe und Aktionen (2026-10-05)

- `set_properties` auf 2.4, 4.10, 4.11, 4.12 und die Aktionen siid 4 aiid 2, 4, 5, 6, 7 sowie
  siid 2 aiid 1 (`start-cook`) antworten alle mit `code 0`.
- Aktionsparameter werden als einfache Werteliste akzeptiert: `{"did", "siid", "aiid", "in": [30]}`.
  Ausgaben kommen als `"out": [{"piid": 8, "value": true}]`.
- **Keiner dieser Aufrufe hatte eine sichtbare Wirkung**: gesetzte Werte erscheinen nicht am Display,
  `start-cook` startet nichts (getestet mit mode 0 und 5, mit und ohne `on = true`).
  Gesetzte Werte lesen sich aber zurück – die Properties wirken wie ein Speicher ohne Anbindung an
  die Koch-App.

## Offene Fragen

Q1–Q8 siehe KICKSTART.md §1. Antworten werden hier mit Datum und Experiment-Referenz (E1–E6) nachgetragen.
