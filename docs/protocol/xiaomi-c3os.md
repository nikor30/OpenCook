# Protokoll `chunmi.mfcp.c3os` (Xiaomi Smart Cooking Robot EU)

**Version:** 0.0 – nur öffentliche MIoT-Spec, noch nichts am Gerät verifiziert.
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
| 6–9  | reserved       | div.   | ?       | auslesen & beobachten                      |
| 10   | cook-duration  | uint16 | R/W/N   | 0–14400 s                                  |
| 11   | cook-temp      | uint8  | R/W/N   | 0–180 °C                                   |
| 12   | cook-speed     | uint8  | R/W/N   | 0–100, Mapping zu 20 Display-Stufen offen (Q4) |
| 13   | weigh-activity | bool   | R/W/N   |                                            |
| 14   | remaining-time | uint32 | R/N     | 0–14400                                    |

Actions: set/get-setting, toggle weighing, get remaining time, set duration/temp/speed, tare
(aiids noch nicht erfasst → Phase 1).

## Netzwerk (beobachtet 2026-10-05, Gerät im Standby)

- Antwortet auf ICMP und auf den miIO-Hello (UDP 54321, 32-Byte-Antwort mit Device-ID und Stamp).
- Das Checksum-Feld der Hello-Antwort ist weder Null noch `ff…`, taugt aber **nicht** als Token:
  ein damit verschlüsseltes `miIO.info` bleibt unbeantwortet. Der Token muss aus der Cloud kommen.
- TCP 1–65535: alle Ports geschlossen (RST). Kein ADB (5555), kein HTTP, kein RTSP → Q8 für TCP
  beantwortet. UDP-Scan steht noch aus.

## Offene Fragen

Q1–Q8 siehe KICKSTART.md §1. Antworten werden hier mit Datum und Experiment-Referenz (E1–E6) nachgetragen.
