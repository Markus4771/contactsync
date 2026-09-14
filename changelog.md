# Changelog

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
