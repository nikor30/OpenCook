# OpenCook – Kickstart

> Lokale, cloudfreie Steuerung des **Xiaomi Smart Cooking Robot (EU, `chunmi.mfcp.c3os`)**
> mit eigenem Rezept-Format (inkl. Bilder), Web-GUI, Home-Assistant-Anbindung und
> Konvertern für Rezepte anderer Küchenmaschinen.

Dieses Dokument ist der Fahrplan. Jede Phase hat **Ziel → Schritte → Artefakte → Definition of Done**.
Arbeite die Phasen in Reihenfolge ab; Phase 1–3 (Recon & Reverse Engineering) entscheiden,
wie viel von Phase 4+ überhaupt möglich ist.

---

## 0. Leitplanken (vor der ersten Zeile Code lesen)

### Recht
- Reverse Engineering zur **Herstellung von Interoperabilität** mit dem eigenen Gerät ist in DE/EU
  zulässig (§ 69e UrhG / Art. 6 RL 2009/24/EG). Nur am **eigenen Gerät** und mit **eigenem Account**.
- **Keine Xiaomi-/Cookidoo-/Fremd-Inhalte ins Repo** (Rezepttexte, Bilder, Videos, App-Bundles,
  Firmware-Dumps). Die gehören in `research/private/` → steht in `.gitignore`.
- Konverter verarbeiten Rezepte, die der Nutzer selbst besitzt/eingibt. Keine Scraper für
  Bezahlplattformen (Cookidoo o. ä.) — deren AGB verbieten das, und das Repo soll veröffentlichbar bleiben.
- Token, Cloud-Credentials, `ssecurity`, Pcaps → **nie committen** (`.env`, `secrets/`, `*.pcap*` in `.gitignore`).

### Sicherheit (Gerät hat Messer + 1200 W Induktion)
- **Remote-Start nur mit Präsenzbestätigung** am Web-GUI/HA („Ich stehe an der Maschine“), mit Timeout.
- Harte Limits im Code, unabhängig von Rezeptdaten: `temp ≤ 150 °C` manuell (180 °C nur, wenn RE zeigt,
  dass das Gerät das selbst absichert), Drehzahl-Cap über 80 °C, max. Dauer pro Schritt.
- Bei Verbindungsverlust → kein „blindes“ Weiterlaufen der Runner-State-Machine; Gerät bleibt im
  eigenen Sicherheitszustand.
- Firmware-Eingriffe (UART/Flash) sind **optional und zuletzt** – Garantieverlust, Brick-Risiko.

---

## 1. Bekannte Fakten (Stand Recherche 2026-10)

### Hardware
| | |
|---|---|
| Modell EU | `chunmi.mfcp.c3os` (Xiaomi Smart Cooking Robot, MCC01M-1A), WLAN 2,4 GHz |
| Modell CN | `chunmi.mfcp.c3` (Mijia), WLAN 5 GHz – andere Spec! |
| Topf | 2,2 L, 3-lagig Edelstahl, IH 1200 W |
| Temperatur | 35–180 °C (manuell max. 150 °C, 180 °C nur in Rezepten) |
| Motor | 40–12 000 U/min, 20 Stufen vorwärts + 20 rückwärts; über 80 °C max. Stufe 6 |
| Waage | 1–5000 g, ±1 g |
| Display | 8″ Touchscreen, Rezepte mit Video (Annahme: Android/Linux-basiert → in Phase 1 prüfen) |
| Dampfaufsatz | max. 2 kg inkl. Geschirr |

### MIoT-Spec `chunmi.mfcp.c3os` (Quelle: home.miot-spec.com)

**siid 2 – Multifunction Cooking Pot**
| piid | Name | Typ | Zugriff | Werte |
|---|---|---|---|---|
| 1 | status | uint8 | R/N | 0 Standby, 1 Cooking, 3 Paused, 6 Sleep, 8 Error, 11 Complete |
| 2 | mode | uint8 | R/W/N | 0 Stop, 1 Stir-fry, 2 Steam, 3 Stew, 4 Warm, 5 Other |
| 3 | left-time | uint32 | R/N | 0–999999 |
| 4 | on | bool | R/W/N | |
| 5 | fault | uint16 | R/N | 0–9999 |
| 10 | recipe-command | string | R/W | **Format unbekannt → Kernziel RE** |

Actions: `aiid 1` start-cook · `aiid 2` cancel · `aiid 3` pause · `aiid 4` start-recipe-cook(in: piid 10)
Event: `eiid 1` cooking-finished

**siid 3 – Alarm:** piid 1 alarm (bool), piid 2 volume (0–100)

**siid 4 – Automatic Cooker**
| piid | Name | Typ | Zugriff | Werte |
|---|---|---|---|---|
| 3 | cook-id | uint32 | R/N | 0–999999999 |
| 4 | cook-type | uint8 | R/N | 0 Official, 1 Single, 2 Mutable, 4 Recipe |
| 5 | cook-name | string | R/N | |
| 6–9 | reserved | div. | ? | **auslesen & beobachten** |
| 10 | cook-duration | uint16 | R/W/N | 0–14400 s |
| 11 | cook-temp | uint8 | R/W/N | 0–180 °C |
| 12 | cook-speed | uint8 | R/W/N | 0–100 (**Mapping zu 20 Stufen unbekannt**) |
| 13 | weigh-activity | bool | R/W/N | |
| 14 | remaining-time | uint32 | R/N | 0–14400 |

Actions siid 4: set/get-setting, toggle weighing, get remaining time, set duration/temp/speed, tare.

### Offene Fragen (Phase 1–3 beantworten)
- Q1 Format von `recipe-command` – Rezept-ID-Referenz oder vollständiges Rezept-JSON?
- Q2 Lädt das Gerät Rezepte selbst (HTTPS zu chunmi/Xiaomi-CDN) oder schiebt die App sie hin?
- Q3 Drehrichtung (rückwärts) per API setzbar? Evtl. negatives Vorzeichen / Reserved-piid / im recipe-command.
- Q4 Mapping `cook-speed 0–100` ↔ Display-Stufen 1–20 / U/min.
- Q5 Sind `mode`-Werte (Stir-fry/Steam/Stew) eigene Heizkurven?
- Q6 Läuft lokale miIO-Steuerung ohne Cloud-Verbindung (Gerät im isolierten VLAN ohne Internet)?
- Q7 Ist die Waage live auslesbar (Gewicht als Property) oder nur Tara/Toggle?
- Q8 Offene Ports am Gerät (ADB 5555? HTTP? MQTT?), OS-Basis.

---

## 2. Zielarchitektur

```
┌──────────────────────── docker compose ────────────────────────┐
│                                                                │
│  ┌──────────────┐   REST/WS   ┌───────────────────────────┐    │
│  │  web (React) │◄───────────►│  core (FastAPI, Python)    │    │
│  └──────────────┘             │  ├─ drivers/ (Plugin-API)  │    │
│                               │  │   ├─ xiaomi_c3os (miIO) │    │
│                               │  │   └─ simulator          │    │
│                               │  ├─ runner (State Machine) │    │
│                               │  ├─ recipes (ORF-Modell)   │    │
│                               │  ├─ converters/            │    │
│                               │  └─ ha (MQTT Discovery)    │    │
│                               └──────┬──────────┬──────────┘    │
│                                      │          │               │
│                         SQLite + /data/media   MQTT ──► Home Assistant
└──────────────────────────────────────┼─────────────────────────┘
                                       │ miIO UDP 54321 (lokal, Token)
                                ┌──────▼──────┐
                                │ Cooking Robot│  (IoT-VLAN)
                                └─────────────┘
```

### Tech-Stack (Entscheidungen als ADRs festhalten)
| Bereich | Wahl | Grund |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLModel + SQLite | python-miio-Ökosystem ist Python |
| Gerät | `python-miio` (MIoT generic) + eigener async Wrapper | bewährt, kann miIO-Pcaps entschlüsseln |
| Frontend | React + TypeScript + Vite + Tailwind, TanStack Query | Tablet-tauglicher Koch-Modus |
| Live-Status | WebSocket (FastAPI) | Restzeit/Temperatur/Waage live |
| HA | MQTT Discovery (Phase 7), später optional HACS Custom Integration | MQTT = kein HA-Code nötig, sofort nutzbar |
| Bilder | Volume `/data/media`, Thumbnails via Pillow, WebP | |
| Tests | pytest, pytest-asyncio, Playwright (E2E), Hypothesis (Parser) | |
| Qualität | ruff, mypy --strict, pre-commit, conventional commits | |
| CI | GitHub Actions, Multi-Arch Images (amd64/arm64) → GHCR | |

### Kanonisches Rezeptformat „ORF“ (OpenCook Recipe Format)
Alles wird **in** ORF konvertiert und **aus** ORF auf ein Gerät übersetzt. Nie direkt Gerät→Gerät.

```yaml
orf_version: 1
id: 3f1c…                     # UUID
title: Parmesan-Rührei
servings: 4
tags: [frühstück, vegetarisch]
images: [media/abc.webp]
source: { type: manual|converted, origin: "thermomix-text", license: private }
ingredients:
  - { id: i1, name: Eier, amount: 8, unit: pcs }
  - { id: i2, name: Butter, amount: 20, unit: g }
steps:
  - id: s1
    kind: machine              # machine | user | weigh | wait
    title: Butter schmelzen
    text: "{i2} in den Topf geben."
    image: media/step1.webp
    machine:                   # geräteneutral, physikalische Einheiten
      temp_c: 100
      duration_s: 120
      speed: { level: 1, of: 10, direction: reverse }   # normiert auf 10er-Skala
      accessory: none           # none | whisk | steamer | basket
  - id: s2
    kind: weigh
    ingredient: i1
    target_g: 480
  - id: s3
    kind: user
    text: "Deckel schließen, Messbecher aufsetzen."
```

JSON-Schema liegt in `schemas/orf-v1.json` und ist **die** Vertragsgrundlage für Treiber, Konverter, GUI.

### Repo-Layout
```
opencook/
├─ CLAUDE.md               # Projekt-Memory für Claude / Konventionen
├─ KICKSTART.md            # dieses Dokument
├─ docs/
│  ├─ adr/                 # 0001-python-backend.md …
│  ├─ protocol/xiaomi-c3os.md   # Ergebnis RE (öffentlich, ohne Fremdinhalte)
│  └─ speed-mapping.md
├─ schemas/orf-v1.json
├─ core/                   # FastAPI-App
│  ├─ opencook/
│  │  ├─ drivers/{base.py,xiaomi_c3os/,simulator/}
│  │  ├─ runner/
│  │  ├─ recipes/
│  │  ├─ converters/{thermomix_text.py,monsieur_cuisine.py,schema_org.py,xiaomi.py}
│  │  ├─ ha/mqtt.py
│  │  └─ api/
│  └─ tests/{unit,integration,fixtures}/
├─ web/                    # React-App
├─ tools/                  # RE-Hilfsskripte (pcap-decrypt, property-dumper, cloud-client)
├─ research/
│  ├─ notes/               # eigene Notizen (committen ok)
│  └─ private/             # Pcaps, Bundles, Dumps → .gitignore!
├─ docker/
│  ├─ core.Dockerfile
│  └─ web.Dockerfile
├─ docker-compose.yml
└─ .github/workflows/
```

---

## Phase 0 – Projekt-Setup (½ Tag)

**Schritte**
1. Git-Repo anlegen, `main` geschützt, Arbeit auf Feature-Branches, Conventional Commits.
2. `.gitignore` **zuerst**: `.env`, `secrets/`, `research/private/`, `*.pcap*`, `*.apk`, `*.jsbundle`, `/data/`.
3. `pre-commit` mit ruff, mypy, prettier, **gitleaks** (Secret-Scan – wegen Tokens wichtig).
4. Devcontainer (`.devcontainer/`) mit Python 3.12, Node 22, `python-miio`, `mitmproxy`, `wireshark-cli`, `jq`.
5. ADR 0001–0003 schreiben: Backend-Sprache, ORF als Kanon, MQTT-Discovery für HA.
6. CI-Skelett: lint + test auf jedem PR.

**DoD:** leeres Repo baut grün in CI, gitleaks blockt einen Test-Token-Commit.

---

## Phase 1 – Recon: Netzwerk, Token, Properties (1–2 Tage)

**Ziel:** Gerät lokal ansprechen, alle Properties dauerhaft mitloggen, Netzwerkverhalten verstehen.

**Schritte**
1. **Netz vorbereiten**
   - Gerät in eigenes IoT-VLAN/SSID (2,4 GHz). Firewall-Policy: Docker-Host → Gerät UDP 54321 erlaubt.
   - Logging aller DNS-Anfragen und Verbindungen des Geräts (Firewall-Log / Pi-hole / AdGuard).
     → Liste der Cloud-Domains erstellen (`research/notes/domains.md`). Q2 hängt daran.
   - Optional: Port-Mirror auf den AP-Uplink oder Gateway-Capture für Pcaps.
2. **Token holen**
   - [Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor), Server `de`.
   - Token + IP in `.env` (`OC_DEVICE_IP`, `OC_DEVICE_TOKEN`).
3. **Erster Kontakt**
   ```bash
   miiocli device --ip $IP --token $TOKEN info
   miiocli genericmiot --ip $IP --token $TOKEN status
   ```
4. **Port-Scan** `nmap -sS -sU -p- --top-ports 2000 $IP` → Q8 (ADB? HTTP? RTSP?).
5. **Property-Logger** `tools/prop_logger.py`: pollt alle siid/piid (inkl. reserved 6–9) jede Sekunde,
   schreibt JSONL mit Zeitstempel. Läuft während **jeder** Testkochung mit.
6. **Kontrollierte Experimente** (je eins, Logger läuft, Notiz in `research/notes/experiments.md`):
   - E1: manuell 60 s / 40 °C / Display-Stufe 1, 2, 5, 10, 20 → Wert von `cook-speed` notieren → Q4
   - E2: dasselbe rückwärts → ändert sich ein Wert? → Q3
   - E3: Waage aktivieren, 100 g / 500 g auflegen → taucht Gewicht in einer Property auf? → Q7
   - E4: offizielles Rezept starten → `cook-id`, `cook-type`, `cook-name`, `recipe-command` lesen
   - E5: Internet für das Gerät sperren → geht lokale Steuerung noch? Startet ein Rezept noch? → Q6, Q2
   - E6: per API `set cook-temp/duration/speed` + `start-cook` → läuft das Gerät?

**Artefakte:** `docs/protocol/xiaomi-c3os.md` v0.1, `research/notes/*`, Logger-Tool.
**DoD:** Gerät per Skript start/stop/pause steuerbar; Speed-Mapping-Tabelle vorhanden; Q2/Q3/Q4/Q6/Q7 beantwortet oder eingegrenzt.

---

## Phase 2 – Reverse Engineering Rezepte (3–10 Tage, größter Unsicherheitsblock)

**Ziel:** Q1 lösen – Format von `recipe-command` + Rezept-Datenmodell inkl. Bilder/Video-URLs verstehen.
Drei Wege, **in dieser Reihenfolge** (billig → teuer):

### 2a. Mi-Home-Geräte-Plugin analysieren (höchste Erfolgschance)
Die Gerätesteuerung in der Mi-Home-App ist ein React-Native-Plugin, das als JS-Bundle nachgeladen wird.
1. Android-Emulator (AVD, Google-APIs-Image, gerootet) oder altes gerootetes Testhandy.
2. Mi Home installieren, einloggen, Cooking Robot öffnen (Plugin wird geladen).
3. Plugin-Bundle aus dem App-Datenverzeichnis ziehen (`/data/data/com.xiaomi.smarthome/files/…/plugin/…`,
   genauen Pfad per `find … -name "*.jsbundle" -o -name "main.bundle"` ermitteln).
4. Nach `research/private/` kopieren, mit `prettier`/`js-beautify` lesbar machen.
5. Suchen nach: `recipe-command`, `start-recipe-cook`, `siid: 2`, `piid: 10`, `aiid: 4`, `chunmi`, `recipe`,
   `cookId`, `speed`, `reverse`, `/api/`, `https://`.
6. Ergebnis: Serialisierung (JSON? Base64? Protobuf? eigenes Byteformat?) dokumentieren.

### 2b. App ↔ Cloud mitschneiden
1. mitmproxy als System-CA im gerooteten Emulator; Certificate-Pinning ggf. per Frida
   (`frida-server` + universelles SSL-Unpinning-Skript) umgehen.
2. Mi-Cloud-Requests (`*.api.io.mi.com`) sind zusätzlich RC4-verschlüsselt mit `ssecurity`/Nonce →
   Entschlüsseln mit eigener Implementierung analog zu [micloud](https://github.com/Squachen/micloud)
   bzw. dem Token-Extractor (`tools/micloud_decrypt.py`).
3. Rezeptliste öffnen, ein Rezept öffnen, an Gerät senden, „Favorit“ setzen → jeweils Requests isolieren.
4. Ergebnis: Endpunkte + JSON-Struktur eines Rezepts (Schritte, Parameter, Medien-URLs) →
   als **anonymisiertes** Beispiel-Schema in `docs/protocol/`, Rohdaten nur in `research/private/`.

### 2c. Gerät ↔ Cloud/CDN
1. miIO-Pcaps mit Token entschlüsseln (python-miio `devtools/pcapparser.py`).
2. Lädt das Gerät Rezepte direkt per HTTPS? → Domains aus Phase 1. Wenn TLS ohne Pinning: lokaler
   DNS-Override + mitmproxy möglich. Mit Pinning: Ende dieses Pfades ohne Firmware-Zugriff.

### 2d. (optional, zuletzt) Gerät selbst
- Offene Ports (ADB!) aus Phase 1 → falls ADB offen: Paketliste, Rezept-Datenbank, Cache-Pfade.
- UART auf dem Mainboard nur, wenn 2a–2c Q1 nicht lösen. Vorher bewusst entscheiden (Garantie).

**Artefakte:** `docs/protocol/xiaomi-c3os.md` v1.0 (Q1 gelöst), Beispiel-Fixtures (selbst erstellt!) in `core/tests/fixtures/xiaomi/`.
**DoD:** Ein **selbst geschriebenes** Rezept mit ≥ 2 Maschinenschritten lässt sich per `start-recipe-cook`
starten **oder** es ist belegt, dass das Gerät nur Cloud-IDs akzeptiert → dann Fallback „Runner“ (Phase 5) ist der Weg.

> **Entscheidungspunkt nach Phase 2:** ADR „Native Rezepte vs. Schritt-Runner“. Der Runner wird
> in jedem Fall gebaut (er ist auch der Weg für andere Geräte); native Rezepte sind ein Bonus.

---

## Phase 3 – Simulator (1–2 Tage, vor der eigentlichen Implementierung!)

**Ziel:** Entwickeln und testen ohne echtes Gerät (und ohne echtes Kochen).

1. `drivers/simulator/`: implementiert das gleiche Treiber-Interface; simuliert Status-Übergänge,
   Restzeit, Temperaturrampe, Fehlerfälle (Deckel offen, Überhitzung, Verbindungsabbruch).
2. Optional zusätzlich ein **miIO-UDP-Fake-Server**, der aus Phase-1-Logs aufgezeichnete Antworten
   liefert → Integrationstest für den echten Treiber.
3. Docker-Compose-Profil `sim` startet alles mit Simulator.

**DoD:** `docker compose --profile sim up` → Web-GUI kocht ein Rezept komplett „virtuell“ durch.

---

## Phase 4 – Core: Treiber-API, ORF, Persistenz (3–5 Tage)

1. **Treiber-Interface** `drivers/base.py`
   ```python
   class CookerDriver(Protocol):
       capabilities: Capabilities          # temp-range, speed-levels, reverse, scale, steamer, native_recipes
       async def connect(self) -> None: ...
       async def state(self) -> CookerState: ...          # status, temp, speed, remaining, weight, fault
       async def run_step(self, step: MachineStep) -> None: ...
       async def pause(self) -> None: ...
       async def cancel(self) -> None: ...
       async def tare(self) -> None: ...
       def events(self) -> AsyncIterator[CookerEvent]: ...
       async def upload_native(self, recipe: ORFRecipe) -> NativeRef | None: ...  # optional
   ```
2. `xiaomi_c3os`-Treiber: async Wrapper um python-miio (Executor), Polling 1 s + Event-Handling,
   Reconnect mit Backoff, **Safety-Clamp** nach `capabilities`.
3. **Speed-Normalisierung:** ORF nutzt `level/of`; Treiber mappt via Tabelle aus Phase 1 (`docs/speed-mapping.md`).
4. ORF-Pydantic-Modelle ↔ `schemas/orf-v1.json` (Schema generieren, in CI gegen Fixtures validieren).
5. SQLite via SQLModel, Alembic-Migrationen. Medien: Upload → WebP + Thumbnail, Hash-basierte Dateinamen.
6. REST-API: `/recipes` CRUD, `/recipes/{id}/media`, `/devices`, `/devices/{id}/state`, `/cook` (Session),
   WebSocket `/ws/devices/{id}`.

**DoD:** API-Tests grün gegen Simulator; echter Treiber besteht Smoke-Test (start/pause/cancel) am Gerät.

---

## Phase 5 – Runner: Rezept-State-Machine (2–3 Tage)

```
IDLE → AWAIT_PRESENCE → STEP_USER (wartet auf „Weiter“)
                       → STEP_WEIGH (Live-Gewicht bis target_g ± Toleranz)
                       → STEP_MACHINE → RUNNING → (PAUSED) → STEP_DONE → nächster Schritt
                       → ERROR (Fault/Verbindungsverlust) → Benutzer entscheidet
→ FINISHED
```
- Persistiert den Zustand (Neustart des Containers mitten im Kochen → sauber fortsetzen oder abbrechen).
- Präsenz-Gate vor **jedem** Maschinenschritt mit Heizung/Messer, wenn seit letzter Interaktion > X min.
- Benachrichtigungen über HA (Phase 7): „Schritt fertig – jetzt Eier zugeben“.
- Property-based Tests (Hypothesis) für die State-Machine.

**DoD:** Parmesan-Rührei- und Hähnchen-Reis-Rezept laufen im Simulator und einmal real komplett durch.

---

## Phase 6 – Web-GUI (4–6 Tage)

Seiten:
1. **Rezeptliste** – Kacheln mit Bild, Tags, Suche, Filter (Frühstück/Mittag, Zutat im Kühlschrank).
2. **Rezept-Editor** – Zutaten mit IDs, Schritte per Drag&Drop, Schritt-Typ, Maschinenparameter mit
   Validierung gegen Geräte-Capabilities, Bild pro Schritt (Upload/Kamera am Tablet), Portionen skalieren.
3. **Import** – Datei/Text einfügen → Konverter-Vorschau → Korrektur → Speichern.
4. **Koch-Modus** (Tablet, große Schrift, Querformat): aktueller Schritt + Bild, Live-Temp/Restzeit/Waage
   über WebSocket, große Buttons Weiter/Pause/Abbrechen, Präsenz-Bestätigung.
5. **Geräte** – Status, Firmware, Verbindungstest, Speed-Kalibrierung.

Qualität: Playwright-E2E gegen `sim`-Profil, Lighthouse/Barrierefreiheit, Dark Mode.

---

## Phase 7 – Home Assistant (1–2 Tage)

**MQTT Discovery** (`homeassistant/<component>/opencook_<device>/<object>/config`):
| Entität | Typ |
|---|---|
| Status, Aktueller Schritt, Rezeptname | `sensor` |
| Restzeit (s), Temperatur Soll, Drehzahl, Gewicht | `sensor` (mit device_class/unit) |
| Start / Pause / Abbrechen / Weiter | `button` |
| Rezept wählen | `select` |
| Präsenz bestätigt | `switch` (auto-reset) |
| Schritt fertig / Rezept fertig / Fehler | `event` + MQTT-Trigger für Automationen |

Beispiel-Automation in `docs/ha/`: Push aufs Handy bei „Schritt fertig“, Sprachansage über Lautsprecher.
Später optional: HACS-Custom-Integration, die direkt die REST/WS-API nutzt (kein MQTT-Broker nötig).

---

## Phase 8 – Konverter für andere Küchenmaschinen (laufend)

Alle Konverter: `parse(source) -> ORFRecipe` + `render(ORFRecipe) -> target` (wo sinnvoll) +
Konfidenz-Score + Liste unsicherer Felder für die Import-Vorschau.

| Konverter | Eingabe | Hinweis |
|---|---|---|
| `thermomix_text` | Freitext im Stil „10 Min./100°C/Linkslauf/Stufe 1“ | Regex + Grammatik (z. B. `lark`), Stufen 1–10, „Varoma“→100 °C + Dampf, „Sanftrührstufe“ |
| `monsieur_cuisine` | Text/Export Monsieur Cuisine (Smart/Connect) | Stufen 1–10, Turbo; Exportformat erst prüfen |
| `bosch_cookit` | Home Connect API (falls freigegeben) | Verfügbarkeit erst prüfen |
| `schema_org` | JSON-LD `Recipe` von Webseiten | nur Zutaten/Schritte; Maschinenparameter per Heuristik vorschlagen |
| `xiaomi` | Format aus Phase 2 | in beide Richtungen, falls native Rezepte möglich |
| `orf_json/yaml` | eigener Export | verlustfrei, für Backup und Teilen eigener Rezepte |

**Speed-Mapping zwischen Geräten** über physikalische Größe (U/min) statt Stufen, Tabelle pro Gerät
in `converters/speed_tables.yaml`. Temperatur-Clamp auf Ziel-Capabilities, Warnung statt stiller Änderung.

Testdaten: **selbst geschriebene** Beispielrezepte in jedem Format + Golden-Files.

---

## Phase 9 – Betrieb (1 Tag)

- `docker-compose.yml`: `core`, `web` (nginx static), optional `mosquitto`; Healthchecks; `restart: unless-stopped`.
- `network_mode: host` **nicht** nötig (miIO ist Unicast), aber Route ins IoT-VLAN sicherstellen.
- Volumes: `/data/db`, `/data/media`; nächtliches Backup (SQLite `.backup` + Medien-Tar).
- Multi-Arch-Images (amd64/arm64) über GitHub Actions → GHCR; Renovate für Dependencies.
- Konfiguration nur über ENV + `/data/config.yaml`; Secrets per Docker secrets.
- Reverse-Proxy (Traefik/NPM) + Auth (mind. Basic Auth / Authelia), **nicht** ins Internet exponieren.

---

## Arbeitsweise wie ein Profi

- **Ein Ticket pro Experiment / Feature**, Ergebnis immer in `research/notes` oder `docs/` – nichts nur im Kopf.
- **Vertrag zuerst:** Schema/Interface + Tests vor Implementierung (ORF-Schema, Treiber-Protocol, API via OpenAPI).
- **Kleine PRs**, CI muss grün sein, Self-Review per Diff.
- **ADRs** für jede Entscheidung, die man später bereuen könnte.
- **Kein Code gegen das echte Gerät ohne Simulator-Test vorher.**
- Versionierung: SemVer, `CHANGELOG.md` per Conventional Commits generiert.

## Meilensteine

| MS | Inhalt | Ergebnis |
|---|---|---|
| M1 | Phase 0–1 | Gerät lokal steuerbar, Speed-Mapping bekannt |
| M2 | Phase 2–3 | Protokoll dokumentiert, Simulator läuft |
| M3 | Phase 4–5 | Eigenes Rezept kocht real per Runner |
| M4 | Phase 6–7 | Web-GUI + HA im Alltag nutzbar |
| M5 | Phase 8–9 | Konverter, Release v1.0 |

---

## Prompts für Claude-Sessions (pro Phase kopieren)

**Phase 0**
> Lies CLAUDE.md und KICKSTART.md. Setze Phase 0 um: Repo-Skelett laut Layout, .gitignore, pre-commit
> (ruff, mypy, prettier, gitleaks), Devcontainer, CI-Workflow, ADR 0001–0003. Kleine Commits.

**Phase 1**
> Schreibe `tools/prop_logger.py`: liest per python-miio (MIoT) alle Properties von `chunmi.mfcp.c3os`
> laut docs/protocol (inkl. siid 4 piid 6–9) jede Sekunde, schreibt JSONL, CLI mit argparse, ENV für IP/Token.
> Dazu `tools/experiment.py`, das E1–E6 aus KICKSTART.md geführt durchläuft und Notizen-Vorlagen erzeugt.

**Phase 2a**
> In `research/private/plugin/` liegt das beautifizierte Mi-Home-Plugin-Bundle. Finde alle Stellen, an denen
> `recipe-command`/siid 2 piid 10/aiid 4 erzeugt werden, rekonstruiere die Serialisierung und dokumentiere sie
> in docs/protocol/xiaomi-c3os.md – ohne Code aus dem Bundle zu übernehmen.

**Phase 3–5**
> Implementiere `CookerDriver`-Protocol, Simulator und Runner-State-Machine laut KICKSTART.md, mit pytest +
> Hypothesis-Tests. Danach den xiaomi_c3os-Treiber mit Safety-Clamps.

**Phase 6–8** analog – immer: „laut KICKSTART.md Phase X, Tests zuerst, ORF-Schema ist Vertrag“.

---

## Quellen
- MIoT-Spec EU: https://home.miot-spec.com/spec/chunmi.mfcp.c3os
- MIoT-Spec CN: https://home.miot-spec.com/spec/chunmi.mfcp.c3
- python-miio: https://github.com/rytilahti/python-miio
- Token-Extractor: https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor
- micloud: https://github.com/Squachen/micloud
- hass-xiaomi-miot: https://github.com/al-one/hass-xiaomi-miot
- Xiaomi FAQ (Specs): https://www.mi.com/global/support/faq/details/KA-12464/
- HA MQTT Discovery: https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
