# Experimente am Gerät

Rohlogs (JSONL vom `tools/prop_logger.py`) liegen in `research/private/logs/` und werden nicht committet.
Zeiten in UTC. Firmware `1.0_179`.

## 2026-10-05 – E1 manueller Lauf vorwärts (60 s / 40 °C, am Display gestartet)

Nur ein Lauf statt der geplanten fünf Stufen; Stufe nicht notiert.

| Zeit | Änderung |
| --- | --- |
| 09:41:23 | 2.2 mode 0 → 5 (Other), rund eine Minute vor dem Start |
| 09:42:22 | 4.5 cook-name → `Handbuch` |
| 09:42:23 | 2.1 status → 1, 4.3 cook-id → 1, 4.14 remaining-time zählt ab 57 |
| 09:42:56 | 2.1 status → 3 (Paused), remaining-time bleibt bei 29 stehen |
| 09:43:37 | 2.1 status → 1 |
| 09:44:07 | 2.1 status → 11 (Complete) |
| 09:44:21 | 2.1 status → 0 |

Unverändert über den ganzen Lauf: 4.10 cook-duration, 4.11 cook-temp, 4.12 cook-speed (alle 0),
4.6/4.7/4.9 (0), 4.8 (true), 2.3 left-time (0), 2.4 on (false).

**Ergebnis:** Status, Pause und Restzeit sind lesbar; die eingestellten Parameter nicht. Q4 lässt sich
durch Mitlesen nicht beantworten.

## 2026-10-05 – E2 manueller Lauf rückwärts (60 s)

09:44:32 status → 1, remaining-time ab 60; 09:45:33 status → 11; 09:45:47 status → 0.
Sonst keine Änderung, insbesondere nicht in 4.6–4.9 oder 4.12.

**Ergebnis:** Die Drehrichtung ist in keiner Property sichtbar (Q3, Lesezugriff). Setzen per API offen.

## 2026-10-05 – E3 Waage (100 g, dann 500 g, am Display aktiviert)

Zwischen 09:45:47 und 09:47:53 keine einzige Property-Änderung. 4.13 weigh-activity blieb `false`.

**Ergebnis:** Das Gewicht ist über die Properties nicht lesbar, und die am Display aktivierte Waage
spiegelt sich nicht in 4.13 (Q7). Die Spec kennt auch keine Gewichts-Property. Offen: ob
`switch-weigh` (siid 4 aiid 3) per API etwas auslöst.
