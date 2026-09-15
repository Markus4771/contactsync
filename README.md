# ContactSync Professional

Modulare Kontakt-, Kunden-, Geräte- und Automatisierungszentrale für Debian mit FastAPI, SQLite und Weboberfläche.

## Aktueller Entwicklungsstand

**Version 3.5.4 – Release-Kandidat im Testkanal**

Der Branch `agent/3.5.4-security` enthält den aktuellen 3.5.4-Release-Kandidaten. Security-, Migrations- und Paket-Regressionstests laufen automatisiert unter Python 3.11 und 3.12; der Debian-Paket-Build wird ebenfalls über GitHub Actions geprüft. Vor der Freigabe für den Produktivbetrieb steht noch der abschließende reale Upgrade-Test auf dem Debian-Testserver sowie die Übernahme nach `main` aus.

## Installation auf Debian direkt über GitHub

### Voraussetzungen

- Debian 12 oder Debian 13
- Root- bzw. sudo-Rechte
- Internetzugang zu GitHub
- Port 8000 für direkten Testzugriff bzw. ein vorhandener Reverse Proxy

### 3.5.4-Testversion installieren

Für einen Testserver ist keine lokale Git-Kopie erforderlich. Der Installer wird direkt aus GitHub geladen und lädt anschließend selbst den vollständigen gewünschten ContactSync-Stand von GitHub.

```bash
wget -O install.sh https://raw.githubusercontent.com/Markus4771/contactsync/agent/3.5.4-security/install.sh
chmod +x install.sh
sudo ./install.sh --test
```

Falls `wget` nicht vorhanden ist:

```bash
curl -fL https://raw.githubusercontent.com/Markus4771/contactsync/agent/3.5.4-security/install.sh -o install.sh
chmod +x install.sh
sudo ./install.sh --test
```

`--test` installiert den Branch `agent/3.5.4-security`. Das Skript lädt die Anwendung vollständig von GitHub, installiert die benötigten Debian-Pakete und Python-Abhängigkeiten, richtet Webdienst und Automation-Worker ein, startet beide Dienste und führt abschließend einen Health-Check durch.

Installationspfade:

- Anwendung: `/opt/contactsync-professional`
- Datenbank und persistente Daten: `/var/lib/contactsync-professional`
- Webdienst: `contactsync-professional.service`
- Automation-Worker: `contactsync-automation.service`

Bei einer erneuten Installation bleiben die persistenten Daten unter `/var/lib/contactsync-professional` erhalten. Existiert bereits eine SQLite-Datenbank, legt der Installer vor dem Upgrade zusätzlich `/var/lib/contactsync-professional/contactsync.db.pre-upgrade` an. Der vorherige Programmstand wird erst nach einem erfolgreichen Healthcheck entfernt und kann bei einem Installations- oder Startfehler automatisch wiederhergestellt werden.

### Installation prüfen

```bash
systemctl status contactsync-professional.service
systemctl status contactsync-automation.service
curl http://127.0.0.1:8000/health
```

Protokolle anzeigen:

```bash
journalctl -u contactsync-professional.service -n 100 --no-pager
journalctl -u contactsync-automation.service -n 100 --no-pager
```

Die Weboberfläche ist standardmäßig erreichbar unter:

```text
http://SERVER-IP:8000/
```

### Testversion aktualisieren

Für ein Update wird der aktuelle Installer erneut von GitHub geladen und ausgeführt:

```bash
wget -O install.sh https://raw.githubusercontent.com/Markus4771/contactsync/agent/3.5.4-security/install.sh
chmod +x install.sh
sudo ./install.sh --test
```

Der Installer erstellt bei vorhandener Datenbank automatisch das oben genannte Pre-Upgrade-Backup. Bei wichtigen Systemen wird trotzdem eine zusätzliche Sicherung des gesamten Verzeichnisses `/var/lib/contactsync-professional` empfohlen.

### Stable-Version

Der Installer unterstützt auch den Stable-Kanal:

```bash
sudo ./install.sh --stable
```

`--stable` installiert den Stand aus `main`. Solange 3.5.4 noch nicht nach `main` übernommen und als Release veröffentlicht wurde, ist für den Release-Kandidaten ausdrücklich `--test` zu verwenden.

### Bestimmten Branch oder Tag installieren

```bash
sudo ./install.sh --ref BRANCH_ODER_TAG
```

Nach der 3.5.4-Freigabe kann beispielsweise der Release-Tag gezielt installiert werden.

### Fehlersuche

Falls der automatische Health-Check fehlschlägt:

```bash
systemctl --no-pager --full status contactsync-professional.service
systemctl --no-pager --full status contactsync-automation.service
journalctl -u contactsync-professional.service -n 100 --no-pager
journalctl -u contactsync-automation.service -n 100 --no-pager
curl -v http://127.0.0.1:8000/health
```

## Enthaltene Funktionen

- FastAPI-Anwendung mit ContactSync-Weboberfläche
- SQLite-Datenbank mit automatischer Initialisierung und migrationssicherem Bestandsdatenpfad
- versionierte REST-API unter `/api/v1`
- Health-Check unter `/health`
- Kunden- und Ansprechpartnerverwaltung mit Kundennummern
- zentrale Connector-Registry und Plugin-Architektur
- Connectoren für Odoo, Zammad, Nextcloud, 3CX und GLPI
- Geräte-/RMM-Ausbau mit NetLock RMM
- Monitoring mit Checkmk
- Synchronisations- und Automatisierungsfunktionen
- Webdienst und separater Automation-Worker über systemd
- Debian-Paket-Build über GitHub Actions
- Session-Authentifizierung und Rollen Admin/Operator/Viewer
- erzwungener Passwortwechsel für den Bootstrap-Administrator
- CSRF-Schutz für schreibende Aktionen
- verschlüsselte und maskierte Connector-Zugangsdaten
- HMAC-signierte Webhooks
- automatisierte Regressionstests für ein Upgrade vorhandener 3.3.x-Kunden- und Ansprechpartnerdaten

## Wichtiger Hinweis zu 3.5.4

Der 3.5.4-Stand hat die automatisierten Security-, Upgrade- und Paketprüfungen vor dem finalen Versions-Bump erfolgreich durchlaufen. Nach dem Versions-Bump wird derselbe Stand nochmals vollständig in CI geprüft. Bis zusätzlich der reale Upgrade-Test auf dem vorgesehenen Debian-Testserver abgeschlossen, PR #16 freigegeben und nach `main` übernommen wurde, bleibt 3.5.4 ein Release-Kandidat und sollte nicht als produktiv freigegeben betrachtet werden.

NetLock Public API ist vorbereitet, aber noch nicht mit realen Benutzer-Credentials verifiziert. 3CX Company Phonebook Write bleibt ohne verifizierten offiziellen Endpoint bewusst deaktiviert.

## Entwicklung

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
export CONTACTSYNC_DATA_DIR="$PWD/.data"
uvicorn contactsync.main:app --reload
```

Tests starten:

```bash
pytest
```

## REST-API

Wichtige Endpunkte sind unter anderem:

- `GET /health`
- `GET /api/v1/dashboard`
- `GET /api/v1/connectors`
- `PATCH /api/v1/connectors/{connector_key}`
- `POST /api/v1/sync`
- `GET /api/v1/sync-runs`
- `GET /docs`

Weitere APIs werden durch die aktivierten Plugins bereitgestellt.
