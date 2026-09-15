# ContactSync Professional – Übergabe für neuen Chat

**Stand:** 15.09.2026  
**Repository:** `Markus4771/contactsync`  
**Aktiver Entwicklungsbranch:** `agent/3.5.4-security`  
**Release-Ziel:** ContactSync Professional 3.5.4 stabil fertigstellen, danach 3.6.0 Asset-Zentrale fortsetzen.

## Anweisung für den neuen Chat

Lies diese Datei vollständig und führe die Entwicklung von ContactSync Professional ab dem hier dokumentierten Stand weiter. Prüfe vor Änderungen den aktuellen GitHub-Stand des Branches `agent/3.5.4-security`; GitHub ist die maßgebliche Quelle. Keine bereits erledigten Arbeiten erneut planen. Bei Freigaben wie „ja“, „ok“, „weiter“, „umsetzen“ oder „Punkt N“ die vereinbarte Entwicklung konkret im Repository umsetzen, Tests/CI prüfen und Ergebnisse nicht nur beschreiben.

## Aktueller Gesamtstand

ContactSync Professional ist eine modulare Kontakt-, Kunden-, Geräte-, Monitoring- und Automatisierungsplattform auf FastAPI/Uvicorn/SQLite für Debian. Die vorhandene Installation auf dem realen Testserver wurde von Version 3.3.0 auf den aktuellen 3.5.4-Teststand aktualisiert. Die Anwendung läuft wieder über Port 8000 und `/health` liefert `status: ok`.

Die interne Versionsnummer ist noch **3.5.1**. Sie soll erst nach Abschluss der noch offenen 3.5.4-Arbeiten überall auf **3.5.4** angehoben werden.

## Aktuell bestätigter GUI-Stand

Die Systemzentrale unter `/` wurde am 15.09.2026 wiederhergestellt und auf dem realen Testserver visuell bestätigt. Statt der früheren weißen FastAPI-Minimalstartseite erscheint jetzt das ContactSync-Dashboard im vorhandenen Design.

Sichtbare Bereiche:
- Kunden & Kontakte
- Geräte & Monitoring
- Störungen
- Synchronisation
- Automatisierung
- Connectoren
- Navigation zu Dashboard, Geräte, Störungen, Automatisierung und REST-API

**Punkt 1 „richtige ContactSync-GUI wieder als Startseite“ ist GRÜN.**

Letzter Commit für die Systemzentrale: `0a62ef8964cffc2f1785c735f1b8c6ce5d164ff9`.

## Reeller Upgrade-Test 3.3.0 → 3.5.4-Teststand

Beim ersten realen Upgrade wurden zwei Release-Blocker gefunden:

1. Der GitHub-Installer erzeugte das Python-Venv unter `/opt/contactsync-professional.new` und verschob es anschließend. Die Python-Entry-Points behielten dadurch Shebangs wie `/opt/contactsync-professional.new/venv/bin/python3.13` und systemd scheiterte mit `203/EXEC`.
2. `pyproject.toml` verwies auf `contactsync.main:run`, obwohl in `contactsync/main.py` keine `run()`-Funktion vorhanden war.

Beide Fehler wurden im GitHub-Branch dauerhaft korrigiert:
- eigener Start-Entry-Point `contactsync.runner:main`
- Venv wird am endgültigen Installationspfad aufgebaut
- Installer prüft Entry-Point/Interpreterpfad
- Rollback auf vorherigen Programmstand vorgesehen

Wichtiger Installer-Fix-Commit: `121ebfaf3c3eb0e4b68924798f72d0ac86112418`.

Der korrigierte Installer wurde anschließend auf dem realen Testserver erneut ausgeführt. Installation/Upgrade und Healthcheck liefen ohne die vorher notwendigen manuellen Reparaturen erfolgreich durch. Damit ist der Installer-/Upgrade-Teil aktuell GRÜN.

## CI-Stand

Nach dem Installer-Fix waren die GitHub-Actions erfolgreich:
- Tests #434: erfolgreich
- Debian-Paket #132: erfolgreich

Nach späteren Änderungen (insbesondere Systemzentrale) vor neuen Aussagen immer den aktuellen CI-Stand erneut aus GitHub abrufen. Nicht automatisch annehmen, dass ältere grüne Runs den neuesten Commit abdecken.

## Security 3.5.4

Vorhanden sind u. a.:
- Secret-Verschlüsselung mit Fernet
- Scrypt-Passwort-Hashes
- Sessions
- CSRF-Schutz
- Rollen `administrator`, `operator`, `viewer` mit Anzeigenamen Admin/Operator/Viewer
- Bootstrap-Admin `admin / admin123`
- erzwungener Passwortwechsel beim Bootstrap-Admin
- Benutzerverwaltung per API
- Webhook-HMAC-Signaturen
- verschlüsselte Connector-Konfigurationen

Wichtige Dateien:
- `contactsync/security.py`
- `contactsync/auth.py`
- `contactsync/security_api.py`
- `contactsync/security_guard.py`
- `contactsync/secure_config.py`

Der Bootstrap-Hash wurde bereits korrigiert; die historische Vorgabe `admin/admin123` darf beim Erststart funktionieren, obwohl normale neue Passwörter mindestens 10 Zeichen verlangen.

### NÄCHSTER AKTIVER PUNKT

**Punkt 2: Security-Tests für 3.5.4 vervollständigen.**

Zu testen sind insbesondere:
1. frische DB: Bootstrap-Login mit `admin/admin123`
2. Login meldet Rolle Admin und `must_change_password`
3. normale geschützte API ist bis zum Passwortwechsel blockiert
4. Passwortwechsel auf ein gültiges Passwort (>=10 Zeichen)
5. alte Session/alter Login verhält sich danach wie vorgesehen; Login mit neuem Passwort funktioniert
6. Admin kann Benutzer auflisten und anlegen
7. Rollen administrator/operator/viewer und Anzeigenamen Admin/Operator/Viewer
8. doppelter Benutzername liefert erwarteten Konflikt
9. Operator/Viewer dürfen Admin-Benutzerverwaltung nicht verwenden
10. Admin darf das eigene aktive Konto nicht selbst deaktivieren
11. Deaktivierung eines anderen Benutzers invalidiert dessen Sessions

Vor Umsetzung die aktuellen Fassungen von `tests/test_security.py`, `tests/test_api.py`, `contactsync/auth.py`, `contactsync/security_api.py`, `contactsync/security_guard.py` und `contactsync/database.py` aus GitHub lesen. DB-Isolation der Tests beachten.

## Datenbank / technische Schulden

Die CI-Fehler bei Geräte-/Kundenbeziehungen wurden zuletzt durch eine taktische Synchronisierung des zentralen DB-Providers behoben. Die Tests für Python 3.11/3.12 und Debian waren danach grün.

Es bestehen noch technische Schulden:
- `main.py` besitzt historisch noch eine eigene DB-Pfad-/`db()`-Implementierung; langfristig sollte `contactsync.database` die einzige Quelle sein.
- Schema-Initialisierung von RMM/Monitoring ist teilweise taktisch über die Secret-Migration gekoppelt.
- NetLock-Plugin registriert noch redundant globale Plattform-Routen.
- direkte GLPI-Geräterouten in `main.py` sind technische Altlast.

Diese Punkte nicht unkontrolliert während der Security-Testarbeit groß refaktorieren. Für 3.5.4 Stabilität vor Architekturumbau.

## Connector-/Funktionsstand

Vorhandene Connectoren/Plugins:
- Odoo JSON-RPC
- Zammad REST
- Nextcloud CardDAV
- 3CX OAuth/XAPI read
- GLPI REST
- NetLock RMM Public API-Grundlage
- Checkmk Monitoring

3CX Company Phonebook Write ist weiterhin nicht implementiert, solange kein verifizierter offizieller Endpoint vorliegt.

NetLock Public API wurde auf Basis offizieller Dokumentation vorbereitet; es gab noch keinen Live-Test mit Benutzer-Credentials.

## Sync Engine

3.5.2-Arbeiten existieren teilweise:
- Sync Preview
- Mapping
- Identitätslogik
- create/update/unchanged/conflict/duplicate/delete-Kategorien
- Preview/Audit-Grundlagen

Aber der eigentliche Automation Worker ist noch nicht vollständig auf die neue Sync Engine umgestellt. Konfliktlogik, Delete, Retry/Checkpointing und Audit-Integration sind noch nicht releasefertig. Für 3.5.4 derzeit keine neue Feature-Ausweitung; zuerst Stabilität/Security abschließen.

## 3.6.0 Asset-Zentrale

Die Entwicklung wurde bereits begonnen, ist aber bewusst pausiert, bis 3.5.4 sauber fertig ist. Vorhandene Arbeiten umfassen Asset Core/API/Matching sowie Beziehungen zu managed_devices, Kunden und Monitoring. Nach 3.5.4 dort fortsetzen.

## Release-Plan 3.5.4

Aktuelle Reihenfolge:

1. GUI/Systemzentrale wieder als Startseite – **GRÜN**
2. Security-Tests vervollständigen – **NÄCHSTER PUNKT**
3. bei Testfehlern nur notwendige Security-/Auth-Fixes durchführen
4. aktuelle CI auf Python 3.11 und 3.12 grün bekommen
5. Debian-Paket erneut grün bauen
6. vorhandene 3.3.0-Kunden/Kontakte nach Upgrade prüfen
7. finalen GitHub-Installer/Upgrade nochmals prüfen, falls relevante Änderungen erfolgten
8. Versionsnummern von 3.5.1 auf 3.5.4 setzen (`contactsync/__init__.py`, `pyproject.toml`, Tests, `version.txt` und weitere Treffer)
9. Changelog/Release-Dokumentation aktualisieren
10. PR #16 prüfen, aus Draft nehmen wenn vollständig grün, dann erst mergen
11. Tag/Release 3.5.4 erstellen und sicherstellen, dass der Stable-Installer auf `main` zeigt
12. danach 3.6.0 Asset-Zentrale fortsetzen

## Pull Request

PR #16: `ContactSync 3.5.4 Security hardening` gegen `main`. Er war zuletzt noch Draft und nicht gemergt. Status vor jeder Release-Aktion aktuell aus GitHub prüfen.

## Installation Testkanal

Der Testkanal verwendet den Branch `agent/3.5.4-security`. Auf Debian wurde zuletzt über `install.sh --test` aktualisiert. Daten liegen unter `/var/lib/contactsync-professional`, Programm unter `/opt/contactsync-professional`, Dienst `contactsync-professional.service`, Port 8000.

Die vorhandenen Produktiv-/Testdaten niemals für Fehlersuche löschen. Vor riskanten Migrationen Backup vorsehen.

## Entwicklungsregeln / Nutzerwünsche

- bestehendes GUI-Design beibehalten, kein unnötiges Redesign
- Odoo/Zammad-Seiten: Verbindung/Einstellungen/Status/Aktionen; Sync-Richtung zentral unter Synchronisation
- Backup und Updates unter Einstellungen, nicht als Hauptmenüpunkt
- Kunden/Firmen besitzen Kundennummer; Ansprechpartner besitzen eigene E-Mail/Telefon/Mobil
- modularer Plugin-Aufbau, passend für IT-Systemhaus-Automatisierung / IT-Projektzentrale
- Debian-Pakete vor finaler Freigabe real testen
- GitHub ist zentrale Projektdokumentation und Installationsquelle
- keine Produktionsreife behaupten, bevor Tests, Paket, Upgrade und Release tatsächlich bestätigt sind

## Wichtige bekannte Versionslage

Trotz 3.5.4-Entwicklungsbranch zeigt die Anwendung aktuell noch **Version 3.5.1**. Das ist absichtlich noch nicht final umgestellt. Erst nach erfolgreichem Security-/Release-Test auf 3.5.4 bumpen.

## Start im neuen Chat

Empfohlene erste Benutzeranweisung:

> Lies bitte die Datei `NEUER-CHAT.md` aus meinem GitHub-Projekt `contactsync` und führe die Entwicklung ab dem dort dokumentierten Stand weiter.

Der neue Chat soll anschließend unmittelbar mit **Punkt 2 – Security-Tests für 3.5.4** beginnen und den aktuellen GitHub-Stand vorher verifizieren.
