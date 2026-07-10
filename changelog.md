# Changelog

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
