# ContactSync Professional

Modulare Kontakt-, Kunden-, Geräte- und Automatisierungszentrale für Debian mit FastAPI, SQLite und Weboberfläche.

## Aktueller Entwicklungsstand

**Version 3.5.4 – Test-/Entwicklungsstand**

Der Branch `agent/3.5.4-security` enthält den aktuellen Entwicklungsstand von ContactSync Professional 3.5.4. Dieser Stand ist für Testsysteme vorgesehen und noch nicht für den Produktivbetrieb freigegeben.

## Installation auf Debian

### Voraussetzungen

- Debian 12 oder Debian 13
- Root- bzw. sudo-Rechte
- Internetzugang zum Herunterladen des öffentlichen GitHub-Repositories
- Port 8000 für den direkten Testzugriff bzw. ein vorhandener Reverse Proxy

### Empfohlene Testinstallation von GitHub

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/Markus4771/contactsync.git
cd contactsync
git switch agent/3.5.4-security
chmod +x install.sh
sudo ./install.sh
```

Das Installationsskript richtet ContactSync unter `/opt/contactsync-professional` ein, legt das Datenverzeichnis `/var/lib/contactsync-professional` an, installiert die Python-Abhängigkeiten in einer virtuellen Umgebung und aktiviert den systemd-Dienst `contactsync-professional.service`.

### Installation prüfen

```bash
systemctl status contactsync-professional.service
curl http://127.0.0.1:8000/health
```

Die letzten Protokollmeldungen können mit folgendem Befehl angezeigt werden:

```bash
journalctl -u contactsync-professional.service -n 100 --no-pager
```

Die Weboberfläche ist standardmäßig erreichbar unter:

```text
http://SERVER-IP:8000/
```

Für einen späteren externen Zugriff wird ein Reverse Proxy wie Nginx bzw. Nginx Proxy Manager empfohlen.

### Testversion aktualisieren

Im geklonten Repository:

```bash
cd contactsync
git switch agent/3.5.4-security
git pull
sudo ./install.sh
```

Vor Updates eines bereits mit produktiven Daten verwendeten Systems sollte eine Sicherung des Datenverzeichnisses `/var/lib/contactsync-professional` erstellt werden.

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
- neue Sicherheitsfunktionen in 3.5.4: Session-Authentifizierung, Rollen, CSRF-Schutz und verschlüsselte Connector-Zugangsdaten

## Wichtiger Hinweis zu 3.5.4

3.5.4 befindet sich noch in der Fertigstellung. Der Debian-Paket-Build funktioniert bereits, aber die vollständige Testsuite ist noch nicht grün. Insbesondere Datenbank-Isolation, Field-Mapping, einzelne geschützte Device-API-Tests und die NetLock-Routenregistrierung werden noch bearbeitet. Daher zunächst nur auf einem Testserver einsetzen und keine produktiven Zugangsdaten verwenden.

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
