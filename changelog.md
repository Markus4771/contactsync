# Changelog

## 3.4.9

- RMM-Gerätebestand mit Hostname, IP, MAC, Betriebssystem, Seriennummer, Agentstatus und letztem Kontakt ergänzt.
- Geräte werden über die Kundennummer dem zentralen ContactSync-Kundenstamm zugeordnet.
- Geräteereignisse `device.new`, `device.offline` und `device.customer_changed` ergänzt und an die Automatisierungsschicht angebunden.
- REST-API für Geräteimport, Suche, Detailansicht und GLPI-Asset-Verknüpfung ergänzt.
- NetLock RMM als sechstes integriertes Connector-Plugin registriert.
- NetLock-Transport bleibt bis zur Verifikation der tatsächlich eingesetzten API-Endpunkte bewusst deaktiviert.
- Release-, Debian-Paket- und Regressionstests auf 3.4.9 erweitert.

## 3.4.8

- Beschaffungsbrücke für externe Bestellautomatisierungen ergänzt.
- Beschaffungsanforderungen mit Status, Kunde, Lieferant, Artikel, Menge, Preis und externer Bestell-ID eingeführt.
- Automationsereignisse für angelegte, freigegebene, bestellte, empfangene und stornierte Beschaffungen ergänzt.
- CLI für Beschaffungsanforderungen und Statusänderungen ergänzt.
- CI auf Python 3.11 und 3.12 abgesichert und Debian-Paketprüfung erweitert.
- GitHub-Releases werden nur noch tag-gesteuert und dynamisch anhand von `version.txt` erzeugt.

## 3.4.7

- GLPI als fünften integrierten Connector-Plugin ergänzt.
- Verbindung über die GLPI REST API mit Benutzer-Token und optionalem App-Token.
- GLPI Entities werden als Kunden/Firmen gelesen, angelegt und aktualisiert.
- GLPI Users werden als Ansprechpartner gelesen, angelegt und aktualisiert.
- Ansprechpartner behalten über `default_entities_id` ihren Kunden-/Entity-Bezug.
- Kundennummer wird für GLPI Entities im Kommentar mit `Kundennummer:` abgelegt und beim Import wieder erkannt.
- Delta-Synchronisation über `date_mod` unterstützt.
- GLPI ist in PluginManager, Health-Check, Connector-API und IT-Projektzentrale-Manifest integriert.
- Release- und Debian-Paketmetadaten auf 3.4.7 aktualisiert.
- Plugin- und Pakettests um GLPI erweitert.

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
