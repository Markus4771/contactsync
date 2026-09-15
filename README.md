# ContactSync Professional

Modulare Kontakt-, Kunden-, Geräte- und Automatisierungszentrale für Debian mit FastAPI, SQLite und Weboberfläche.

## Aktueller Entwicklungsstand

**Version 3.5.4 – Test-/Entwicklungsstand**

Der Branch `agent/3.5.4-security` enthält den aktuellen Entwicklungsstand von ContactSync Professional 3.5.4. Dieser Stand ist für Testsysteme vorgesehen und noch nicht für den Produktivbetrieb freigegeben.

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

`--test` installiert den Branch `agent/3.5.4-security`. Das Skript lädt die Anwendung vollständig von GitHub, installiert die benötigten Debian-Pakete und Python-Abhängigkeiten, richtet den systemd-Dienst ein, startet ContactSync und führt abschließend einen Health-Check durch.

Installationspfade:

- Anwendung: `/opt/contactsync-professional`
- Datenbank und persistente Daten: `/var/lib/contactsync-professional`
- systemd-Dienst: `contactsync-professional.service`

Bei einer erneuten Installation bleiben die persistenten Daten unter `/var/lib/contactsync-professional` erhalten.

### Installation prüfen

```bash
systemctl status contactsync-professional.service
curl http://127.0.0.1:8000/health
```

Protokoll anzeigen:

```bash
journalctl -u contactsync-professional.service -n 100 --no-pager
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

Vor Updates eines Systems mit wichtigen Daten sollte `/var/lib/contactsync-professional` gesichert werden.

### Stable-Version

Der Installer unterstützt auch den Stable-Kanal:

```bash
sudo ./install.sh --stable
```

`--stable` installiert den Stand aus `main`. Solange 3.5.4 noch nicht freigegeben und nach `main` übernommen wurde, ist für Tests ausdrücklich `--test` zu verwenden.

### Bestimmten Branch oder Tag installieren

```bash
sudo ./install.sh --ref BRANCH_ODER_TAG
```

Nach einer späteren 3.5.4-Freigabe kann beispielsweise ein entsprechender Release-Tag gezielt installiert werden.

### Fehlersuche

Falls der automatische Health-Check fehlschlägt:

```bash
systemctl --no-pager --full status contactsync-professional.service
journalctl -u contactsync-professional.service -n 100 --no-pager
curl -v http://127.0.0.1:8000/health
```

## Enthaltene Funktionen

- FastAPI-Anwendung mit Weboberfläche
- SQLite-Datenbank mit automatischer Initialisierung
- versionierte REST-API unter `/api/v1`
- Health-Check unter `/health`
- Kunden- und Ansprechpartnerverwaltung
- zentrale Connector-Registry und Plugin-Architektur
- Connectoren unter anderem für Nextcloud, Zammad, Odoo und 3CX
- Geräte-/RMM- und Monitoring-Ausbau mit NetLock RMM und Checkmk
- Synchronisations- und Automatisierungsfunktionen
- systemd-Dienst
- Debian-Paket-Build über GitHub Actions
- Sicherheitsfunktionen in 3.5.4: Session-Authentifizierung, Rollen, CSRF-Schutz und verschlüsselte Connector-Zugangsdaten

## Wichtiger Hinweis zu 3.5.4

3.5.4 befindet sich noch in der Fertigstellung. Der Debian-Paket-Build funktioniert bereits, die vollständige Testsuite ist jedoch noch nicht grün. Der aktuelle Teststand sollte deshalb zunächst nur auf einem Testserver eingesetzt werden. Produktive Zugangsdaten sollten erst nach Abschluss der Security- und Integrationstests verwendet werden.

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
