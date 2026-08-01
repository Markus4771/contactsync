# ContactSync Professional

Modulare Kontakt- und Verzeichniszentrale für Debian mit FastAPI, SQLite und Weboberfläche.

## Aktueller Entwicklungsstand

**Version 3.3.0**

Version 3.3.0 legt erstmals einen ausführbaren Anwendungskern direkt im GitHub-Repository ab. Der frühere Repository-Stand enthielt nur Projektdokumentation.

## Enthaltene Funktionen

- FastAPI-Anwendung mit Web-Dashboard
- SQLite-Datenbank mit automatischer Initialisierung
- versionierte REST-API unter `/api/v1`
- Health-Check unter `/health`
- zentrale Connector-Registry
- Connectoren für Nextcloud, Zammad, Odoo, 3CX, Microsoft 365, LDAP, Mailcow, CSV und vCard
- Connectoren aktivieren, konfigurieren und ihren Status anzeigen
- Voll- und Delta-Synchronisationsaufträge in eine Warteschlange einstellen
- Historie der Synchronisationsläufe
- systemd-Dienst mit abgesicherten Service-Einstellungen
- Debian-Installationsskript
- API-Grundtests

## Installation auf Debian

```bash
git clone https://github.com/Markus4771/contactsync.git
cd contactsync
git switch agent/version-3-3-0
chmod +x install.sh
sudo ./install.sh
```

Nach der Installation:

```bash
systemctl status contactsync-professional.service
curl http://127.0.0.1:8000/health
```

Die Weboberfläche läuft standardmäßig auf Port `8000`. Für den externen Zugriff sollte der vorhandene Nginx Proxy Manager verwendet werden.

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

- `GET /api/v1/dashboard`
- `GET /api/v1/connectors`
- `PATCH /api/v1/connectors/{connector_key}`
- `POST /api/v1/sync`
- `GET /api/v1/sync-runs`
- `GET /docs`

## Noch nicht produktiv fertig

Die Connector-Registry und die Synchronisationswarteschlange sind funktionsfähig. Die tatsächlichen Datentransfers der einzelnen Connectoren, verschlüsselte Zugangsdaten, Hintergrund-Worker, Benutzeranmeldung und das `.deb`-Paket folgen in den nächsten Ausbauschritten von 3.3.x.
