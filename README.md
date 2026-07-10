# ContactSync Professional

Modulare Kontakt-Synchronisationsplattform für Debian 13 mit FastAPI, SQLite und Weboberfläche.

## Aktueller Release

**Version 3.2.09**

Enthalten sind Connectoren für 3CX, Nextcloud CardDAV, Zammad und Odoo, ein zentraler Kundenstamm, Synchronisations-Center, Feldmapping, Backup- und Updateverwaltung sowie eine einfache Benutzerverwaltung.

### Standardanmeldung nach Neuinstallation

- Benutzer: `admin`
- Passwort: `admin123`

Das Passwort sollte nach der ersten Anmeldung unter **Einstellungen → Benutzerverwaltung** geändert werden.

## Installation

```bash
sudo apt install ./dist/contactsync-professional_3.2.09_all.deb
sudo systemctl restart contactsync-professional.service
```

## Dienst prüfen

```bash
systemctl status contactsync-professional.service
journalctl -u contactsync-professional.service -n 100 --no-pager
```

## Versionsstand 3.2.09

- automatische Migration der Benutzertabelle
- Behebung des Fehlers `no such column: active`
- Login und Passwortänderung
- Hilfe im Programm
- Backup auf SMB/NAS
- Export des Kundenstamms als CSV
- Backups und Updates unter Einstellungen
- bearbeitbare Feldmapping-Zeilen

## Sicherheitshinweis

Das Standardpasswort `admin123` ist nur für die Erstinstallation vorgesehen und muss geändert werden.
