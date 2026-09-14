# Changelog

## 3.4.6

- Separaten Automatisierungs-Worker als systemd-Dienst ergänzt.
- SQLite-basierte Event-Queue für Kunden-, Ansprechpartner- und Sync-Ereignisse eingeführt.
- Webhook-Ziele für externe Automatisierungen wie n8n ergänzt.
- Zeitgesteuerte Synchronisationspläne mit konfigurierbarem Intervall eingeführt.
- Synchronisationswarteschlange wird durch den Worker automatisch verarbeitet.
- Sync-Links speichern Quell- und Ziel-IDs für spätere Aktualisierungen statt doppelter Neuanlagen.
- Retry-Logik mit exponentiellem Backoff und Fehlerprotokoll ergänzt.
- Kunden- und Ansprechpartneränderungen erzeugen automatisch Events über SQLite-Trigger.
- Debian-Paket installiert, aktiviert und startet den neuen Automatisierungsdienst.
- IT-Projektzentrale-Manifest und Paketversion vollständig auf 3.4.6 aktualisiert.
- Tests für Automatisierungsschema, Event-Erzeugung, Scheduler, Webhook-Konfiguration und Retry ergänzt.

## 3.4.5

- Zammad-Connector produktiv über REST-API angebunden.
- Zammad Organisationen werden als Kunden/Firmen gelesen und geschrieben.
- Zammad Benutzer werden als Ansprechpartner gelesen und geschrieben.
- Optionales Mapping eines eigenen Zammad-Kundennummernfeldes ergänzt.
- Nextcloud-Connector auf echte CardDAV-Kommunikation umgestellt.
- Nextcloud Kunden und Ansprechpartner werden als vCards gelesen, angelegt und aktualisiert.
- ContactSync-spezifische vCard-Felder für Kundennummer, Entitätstyp und Kundenbezug ergänzt.
- 3CX V20 XAPI Authentifizierung und Verbindungstest implementiert.
- 3CX Benutzerimport paginiert mit maximal 100 Datensätzen pro Anfrage, damit das XAPI-Limit eingehalten wird.
- 3CX Kundendaten und Telefonbuch-Schreibzugriffe bleiben getrennt, solange kein stabil dokumentierter Phonebook-Endpunkt verfügbar ist.
- Zammad-, Nextcloud- und 3CX-Plugin-Version auf 1.2.0 angehoben.

## 3.4.4

- Odoo-Connector auf echte JSON-RPC-Kommunikation umgestellt.
- Verbindungstest mit Odoo-Anmeldung und Serverversionsabfrage ergänzt.
- Kunden/Firmen werden aus `res.partner` gelesen und in das ContactSync-Kundenmodell normalisiert.
- Ansprechpartner werden inklusive Firmenbezug aus `res.partner` gelesen.
- Delta-Abfragen über `write_date` werden unterstützt.
- Kunden und Ansprechpartner können in Odoo angelegt und aktualisiert werden.
- Kundennummer, E-Mail, Telefon, Mobil, Adresse, Website und USt-ID werden übertragen.
- Odoo-Plugin-Version auf 1.2.0 angehoben und als produktiver JSON-RPC-Transport gekennzeichnet.
- Tests decken Lesen, Erstellen, Aktualisieren und Firmenbezug der Ansprechpartner ab.

## 3.4.3

- Einheitliche asynchrone Plugin-Schnittstelle für alle Connectoren eingeführt.
- Standardoperationen: `test_connection`, `fetch_customers`, `fetch_persons`, `create_customer`, `update_customer`, `create_person`, `update_person`.
- Gemeinsame Ergebnisverträge für Verbindungstests und Schreiboperationen ergänzt.
- Noch nicht providerseitig angebundene Operationen liefern einen klar unterscheidbaren `PluginOperationNotImplemented`-Fehler.
- Connector-Metadaten veröffentlichen die verfügbaren Standardoperationen über das Plugin-Registry.
- Tests stellen sicher, dass Odoo, Zammad, 3CX und Nextcloud denselben Schnittstellenvertrag erfüllen.
- IT-Projektzentrale-Manifest kennzeichnet die Schnittstelle als `async-v1`.

## 3.4.2

- Synchronisations-Core vollständig auf den zentralen `PluginManager` umgestellt.
- Connectoren werden nicht mehr aus einer fest eingebauten Liste geladen.
- Odoo, Zammad, 3CX und Nextcloud werden dynamisch aus dem Plugin-Registry bereitgestellt.
- Connector-Konfiguration wird über die jeweilige Plugin-Validierung geprüft.
- Synchronisationsaufträge akzeptieren nur registrierte Connector-Plugins.
- Feldmapping validiert Connectoren gegen das Plugin-Registry.
- Dashboard zählt nur tatsächlich registrierte und aktive Connector-Plugins.
- Health-Check zeigt die Anzahl registrierter Plugins an.
- IT-Projektzentrale-Manifest kennzeichnet den PluginManager als Connector-Registry.

## 3.4.1

- Connector-Plugin-Framework mit Odoo, Zammad, 3CX und Nextcloud vertieft.
- Pflichtkonfiguration und Connector-spezifische Normalisierung ergänzt.

## 3.3.1

- Erweiterter Kundenstamm mit eindeutiger Kundennummer.
- Zentrale E-Mail-Adresse, Telefon, Mobil, Adresse, Webseite und Status ergänzt.
- USt-IdNr., Steuernummer, Debitorennummer, Branche und Vertragsdaten ergänzt.
- Firmen/Kunden und Ansprechpartner getrennt modelliert.
- Mehrere Ansprechpartner pro Kunde mit Hauptansprechpartner möglich.
- REST-API für Kunden und Ansprechpartner ergänzt.
- Zentrales Feldmapping für Connectoren ergänzt.
- Bestehende Kontakte aus 3.3.0 werden bei der Migration in den neuen Kundenstamm übernommen.
- Kundenstamm- und Feldmapping-Seiten in der Weboberfläche ergänzt.

## 3.2.09

- Robuste Datenbankmigration für die Benutzerverwaltung.
- Fehlende Spalte `users.active` wird bei bestehenden Installationen automatisch ergänzt.
- Fehlende Benutzerfelder `password_hash`, `salt`, `is_admin` und `updated_at` werden automatisch ergänzt.
- Ein vorhandener Admin ohne Passwort-Hash wird auf das Erstpasswort `admin123` initialisiert.

## 3.2.08

- Einfache Benutzerverwaltung ergänzt.
- Standardbenutzer `admin` mit Erstpasswort `admin123`.
- Login, Logout und Passwortänderung unter Einstellungen.

## 3.2.07

- Hilfe-Schaltfläche und Hilfeseite ergänzt.
- Kundenstamm als CSV exportierbar.
- SMB-/NAS-Sicherung für Backups und Updatepakete ergänzt.

## 3.2.05

- Backups und Updates aus dem Hauptmenü entfernt.
- Beide Verwaltungsseiten unter Einstellungen eingeordnet.
- Zurück-Schaltflächen und Breadcrumbs ergänzt.

## 3.2.04

- Einzelne Feldmapping-Zeilen können bearbeitet, aktiviert, deaktiviert, ergänzt und gelöscht werden.

## 3.2.03

- Menüpunkt Plugins/Warteschlange entfernt.
- Warteschlange in das Synchronisations-Center verschoben.

## 3.2.02

- Menüpunkt Kontakte entfernt.
- Kundenstamm als zentrale Verwaltung für Firmen und Ansprechpartner festgelegt.

## 3.2.01

- Firmen und Ansprechpartner getrennt modelliert.
- Zammad-Organisationen werden Firmen zugeordnet.
- Zammad-Benutzer werden Ansprechpartnern zugeordnet.
- 3CX-Filter für nicht kundenbezogene Kontakte ergänzt.
