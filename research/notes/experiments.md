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

## 2026-10-05 – E4 offizielles Rezept (am Display gestartet, nach wenigen Sekunden abgebrochen)

| Zeit | Änderung |
| --- | --- |
| 09:49:14 | 2.2 mode 5 → 0 (manuellen Modus verlassen) |
| 09:49:49 | 2.2 mode → 5 |
| 09:49:58 | 4.3 cook-id → 1474, 4.4 cook-type → 4 (Recipe), 4.5 cook-name → Rezepttitel im Klartext |
| 09:50:01 | 2.1 status → 1, 4.14 remaining-time ab 1500 |
| 09:50:06 | 2.1 status → 3 (Paused) bei 1496 |
| 09:50:11 | 2.1 status → 0, 2.2 mode → 0, remaining-time → 0 (Abbruch) |

Unverändert: 2.10 recipe-command (leer), 4.6–4.9, 4.10–4.12, 2.3 left-time.
cook-id, cook-type und cook-name bleiben nach dem Abbruch stehen.

**Ergebnis:** Rezepte haben eine numerische ID (`cook-id`), `cook-type` 4 und den Titel als
`cook-name`. `remaining-time` ist die Dauer des laufenden Schritts bzw. Rezepts (1500 s).
`recipe-command` wird bei einem am Display gestarteten Rezept **nicht** befüllt – das Format (Q1) lässt
sich durch Mitlesen nicht gewinnen. Auch bei Rezepten ist `mode` 5; die Werte 1–4 wurden nie gesehen.

## 2026-10-05 – E6 Steuern per API (30 s / 0 °C / Speed 1 bzw. 5, Nutzer am Gerät)

| Versuch | Antwort | Wirkung |
| --- | --- | --- |
| `get-setting` (4/2), `get-time` (4/4) | code 0, liefern 4.8 = true bzw. 4.14 = 0 | – |
| `set_properties` 4.10 / 4.11 / 4.12 | code 0, Werte lesen sich zurück | Display zeigt weiter 0 |
| `set-duration` / `set-temp` / `set-speed` (4/5–7) | code 0 | Display zeigt weiter 0 |
| `start-cook` (2/1) bei mode 0 | code 0 | nichts: status bleibt 0, Display und Motor reagieren nicht |
| `start-cook` bei mode 5 | code 0 | nichts |
| `set_properties` 2.4 on = true, danach `start-cook` | code 0, 2.4 liest sich als true | nichts |

Zwischendurch (09:54:43) lief ein manueller Lauf über 20 s, den der Logger als `Handbuch` zeigt. Er wurde
nicht per API ausgelöst (letzter Befehl davor 09:51:59); Ursache noch nicht geklärt.

**Ergebnis:** Das Gerät quittiert alle Schreibzugriffe und Aktionen mit code 0, führt aber keine davon
aus. Die schreibbaren Properties verhalten sich wie ein reiner Speicher ohne Verbindung zur Koch-App.
Lokales Starten/Setzen über die Spec-Aktionen funktioniert so nicht (Q3/Q4 weiter offen).
Nach dem Versuch wurden 2.4, 4.10 und 4.12 auf die Ausgangswerte zurückgesetzt.

## 2026-10-05 – E7 `start-recipe-cook` mit bekannter Rezept-ID (Nutzer am Gerät)

`action` siid 2 aiid 4 mit `recipe-command` = `"1474"`, `{"cook_id": 1474}`, `{"id": 1474}`,
`{"recipeId": 1474}` (jeweils als `"in": [<string>]`) sowie `"in": [{"piid": 10, "value": "1474"}]`.
Jede Variante: `code 0`, keine Ausgabe. Innerhalb von 6 s keine Änderung an status, cook-id,
cook-name oder recipe-command. (Display-Beobachtung des Nutzers noch offen.)

**Ergebnis:** Auch `start-recipe-cook` wird quittiert, aber nicht ausgeführt – zumindest nicht mit
einer bloßen Rezept-ID. Zusammen mit E6 ist lokales Starten damit nicht belegt. Eigene Rezepte laufen
deshalb über den Koch-Modus von OpenCook (Anleitung am Tablet, Start am Display).
