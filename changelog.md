# Changelog

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
