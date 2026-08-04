# Installation über die IT-Projektzentrale

ContactSync ist über `projekt.yaml` für die IT-Projektzentrale beschrieben.

Für eine vollständige Installation müssen im GitHub-Release dieselben beiden Dateien vorhanden sein:

- `contactsync-professional_3.2.09_all.deb`
- `contactsync-professional_3.2.09_all.deb.sha256`

Die SHA256-Datei wird automatisch vom Release-Workflow erzeugt. Der Workflow erwartet ein ausführbares Buildskript unter `scripts/build_deb.sh` oder `build_deb.sh`, das das Debian-Paket im Verzeichnis `dist/` erzeugt.

Da das Repository privat ist, muss in der IT-Projektzentrale ein verschlüsseltes GitHub-Token mit Leserechten für dieses Repository hinterlegt und beim Installationsassistenten ausgewählt werden.
