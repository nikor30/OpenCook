# OpenCook

Lokale, cloudfreie Anbindung des **Xiaomi Smart Cooking Robot** (EU, `chunmi.mfcp.c3os`):
eigene Rezepte mit geführtem Koch-Modus, Live-Status im Browser und in Home Assistant, Koch- und
Reinigungsstatistik – alles in einem Docker-Container im eigenen Netz.

> **Nur lesend.** Das Gerät quittiert Schreibbefehle über die lokale Schnittstelle, führt sie aber
> nicht aus (siehe [Protokoll](docs/protocol/xiaomi-c3os.md)). OpenCook liest deshalb nur und
> verändert nichts am Gerät.

<p>
  <img src="docs/screenshots/live-light.png" alt="Live-Status" width="49%" />
  <img src="docs/screenshots/live-dark.png" alt="Live-Status im Dark Mode" width="49%" />
</p>

## Funktionen

- **Eigene Rezepte:** Editor für Zutaten und Schritte (Maschine, Handgriff, Abwiegen, Warten),
  Import aus eingefügtem Text in Thermomix-Schreibweise oder von einer Rezept-URL (schema.org),
  Austausch als ORF-Datei (JSON).
- **Koch-Modus:** zeigt jeden Schritt groß an – bei Maschinenschritten Temperatur, Zeit und Stufe zum
  Einstellen am Display. OpenCook erkennt am Gerätestatus, wann der Schritt läuft und fertig ist,
  und springt zum nächsten. Gedacht für ein Tablet neben dem Gerät.
- **Live:** Status (Bereit, Kocht, Pausiert, Fertig, Nicht erreichbar), Restzeit und Rezept,
  sekündlich aktualisiert. Optional Debug-Werte: Rezept-ID, Typ, Modus und alle Rohwerte.
- **Statistik:** Kochvorgänge, fertig gekochte Rezepte, gesamte Kochzeit, häufigste Rezepte,
  die letzten 30 Tage, Uhrzeiten und die letzten Vorgänge.
- **Reinigung:** eigene Auswertung der Reinigungsprogramme – wann zuletzt gereinigt, und wie oft
  seitdem gekocht wurde.
- **Einstellungen:** IP-Adresse und Token des Geräts direkt im Browser ändern; Debug-Werte ein- und
  ausblenden.
- **Home Assistant:** Integration mit Status, Restzeit, „Fertig um“, Rezept und mehr
  ([Anleitung](docs/ha/README.md)).
- Hell und dunkel, am Handy und am Tablet nutzbar.

## Screenshots

| Statistik (Beispieldaten) | Einstellungen |
| --- | --- |
| <img src="docs/screenshots/stats-light.png" alt="Statistik" width="420" /> | <img src="docs/screenshots/settings-light.png" alt="Einstellungen" width="420" /> |

| Debug-Werte eingeblendet | Handy |
| --- | --- |
| <img src="docs/screenshots/live-debug-light.png" alt="Live-Status mit Debug-Werten" width="420" /> | <img src="docs/screenshots/live-phone.png" alt="Live-Status am Handy" width="260" /> |

Dark Mode: [Statistik](docs/screenshots/stats-dark.png) ·
[Einstellungen](docs/screenshots/settings-dark.png) ·
[Debug-Werte](docs/screenshots/live-debug-dark.png).
Die Statistik-Screenshots zeigen Beispieldaten; Live und Einstellungen stammen vom echten Gerät.
Neu erzeugen mit `tools/screenshots.py` (Aufruf steht im Skript).

## Schnellstart

Voraussetzungen: Docker mit Compose auf einem Rechner im selben Netz wie das Gerät (getestet auf
einem Raspberry Pi), dazu IP-Adresse und Token des Geräts.

```bash
git clone https://github.com/nikor30/OpenCook.git
cd OpenCook
docker compose up -d --build
```

Dann `http://<rechner>:8080` öffnen und unter **Einstellungen** IP-Adresse und Token eintragen.
Alternativ beide Werte vorab in eine `.env` schreiben (Vorlage: `.env.example`); im Browser
gespeicherte Einstellungen haben Vorrang.

**Token holen:** mit dem
[Xiaomi-cloud-tokens-extractor](https://github.com/PiotrMachowski/Xiaomi-cloud-tokens-extractor),
Server `de`. Der Token wird nur im Docker-Volume gespeichert (Datei nur für den Dienst lesbar) und
nie wieder über die API ausgegeben.

**Hinweis:** Die Weboberfläche hat keine Anmeldung. Jeder im Netz kann den Status sehen und die
Einstellungen ändern. Nicht ins Internet freigeben.

## Rezepte und Koch-Modus

Das Gerät lässt sich nicht fernstarten (Experimente E6/E7). Der Koch-Modus führt deshalb durch das
Rezept: Du stellst die angezeigten Werte im manuellen Modus am Display ein und drückst Start;
OpenCook sieht den Start, die Pause und das Ende und zeigt dann den nächsten Schritt. Werte
außerhalb der Gerätegrenzen (35–150 °C, über 80 °C höchstens Stufe 6) werden beim Speichern
angezeigt und blockieren das Kochen.

**Rezepte importieren:** Unter Rezepte → *Text einfügen* den Rezepttext (Titel, Zutaten,
Zubereitung) einfügen. Angaben wie `10 Min./100°C/Linkslauf/Stufe 1` werden zu Maschinenschritten:

| Thermomix | Bimbi |
| --- | --- |
| Stufe 1–10 (auch halbe Stufen) | Stufe 2–20 (verdoppelt; lineare Annahme, echtes Mapping noch offen) |
| Linkslauf | rückwärts |
| Sanftrührstufe | Stufe 1 |
| Varoma | 120 °C mit Dampfaufsatz – wird zum Prüfen markiert |
| Teig-Modus / Knetstufe, Turbo | Stufe 4 bzw. 20 – wird zum Prüfen markiert |

Das Ergebnis öffnet sich im Editor zum Prüfen, bevor es gespeichert wird.

**Von einer Webseite:** Unter Einstellungen → *Rezept von einer Webseite importieren* (oder Rezepte →
*Von Webseite*) eine Rezept-URL eingeben. OpenCook ruft genau diese eine Seite ab, liest die
eingebetteten schema.org-Rezeptdaten (JSON-LD) und wandelt sie wie beim Text-Import um. Dabei gilt:

- nur eine Seite pro Klick, nur Text, keine Bilder; nur für den privaten Gebrauch
- `robots.txt` wird beachtet, Adressen im lokalen Netz werden nicht abgerufen
- gesperrt sind Seiten, deren Nutzungsbedingungen automatisches Auslesen verbieten (Rezeptwelt,
  MixBuch, Cookidoo). Dort den Rezepttext kopieren und *Text einfügen* nutzen.

Mit dem Schalter **Testmodus** prüft OpenCook eine Adresse nur und zeigt jeden Schritt mit ✓ oder ✗
an (Sperrliste, Netz, robots.txt, Abruf, Rezeptdaten, Umwandlung) – praktisch, um herauszufinden,
welche Seiten sich importieren lassen.

Ein Beispielrezept liegt in [docs/examples](docs/examples/).

## Wie gezählt wird

Das Gerät meldet nur, *dass* es läuft und welches Rezept geladen ist. Ein Kochvorgang reicht
deshalb vom ersten Start bis 15 Minuten Ruhe oder bis ein anderes Rezept startet; mehrere Schritte
eines Rezepts zählen als ein Vorgang. Als Kochzeit zählt nur die Zeit mit laufender Maschine.
Reinigungsprogramme erkennt OpenCook am Namen („Reinigung“). Manuelle Läufe im Koch-Modus zählen
als das gekochte Rezept.

## Entwicklung

```bash
pip install -e "core[dev]"     # Python 3.12+
pre-commit install
pytest -q                      # Tests
pre-commit run --all-files     # ruff, mypy --strict, prettier, gitleaks
```

Oder im Devcontainer (`.devcontainer/`), der alles mitbringt. Projektregeln und Fahrplan:
[CLAUDE.md](CLAUDE.md) und [KICKSTART.md](KICKSTART.md), Architekturentscheidungen in
[docs/adr](docs/adr/).

| Pfad | Inhalt |
| --- | --- |
| `core/opencook/drivers/xiaomi_c3os/` | Read-only-Treiber (miIO, nur `get_properties`) |
| `core/opencook/history/` | Erkennung und Speicherung der Kochvorgänge, Statistik |
| `core/opencook/recipes/` | Rezeptformat ORF, Speicherung, Gerätegrenzen |
| `core/opencook/runner/` | Ablauf des Koch-Modus |
| `core/opencook/converters/` | Import aus Thermomix-Text und schema.org (URL-Import) |
| `schemas/orf-v1.json` | JSON-Schema des Rezeptformats (generiert) |
| `core/opencook/api/` | FastAPI-App und Weboberfläche |
| `custom_components/opencook/` | Home-Assistant-Integration |
| `docs/protocol/` | Was über das Geräteprotokoll bekannt ist |
| `tools/` | Property-Logger und Screenshot-Skript |

## Rechtliches

Ein Hobbyprojekt zur Interoperabilität mit dem eigenen Gerät; nicht mit Xiaomi verbunden. Das
Repository enthält keine Inhalte, Firmware oder App-Bestandteile von Xiaomi. Lizenz:
[Apache 2.0](LICENSE).
