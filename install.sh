#!/usr/bin/env bash
set -euo pipefail

REPO="Markus4771/contactsync"
DEFAULT_BRANCH="main"
TEST_BRANCH="agent/3.5.4-security"
CHANNEL="${CONTACTSYNC_CHANNEL:-stable}"
REF="${CONTACTSYNC_REF:-}"
APP_DIR=/opt/contactsync-professional
DATA_DIR=/var/lib/contactsync-professional
DB_FILE="$DATA_DIR/contactsync.db"
DB_BACKUP="$DATA_DIR/contactsync.db.pre-upgrade"
SERVICE_USER=contactsync
MAIN_SERVICE=contactsync-professional.service
AUTOMATION_SERVICE=contactsync-automation.service
TMP_DIR=""

usage() {
  cat <<'EOF'
ContactSync Professional Installer

Usage:
  sudo ./install.sh [--stable|--test] [--ref BRANCH_OR_TAG]

Channels:
  --stable   Installiert den Stand aus main (Standard)
  --test     Installiert den aktuellen 3.5.4-Teststand
  --ref REF  Installiert einen bestimmten Git-Branch oder Tag

Auch per Umgebungsvariable möglich:
  CONTACTSYNC_CHANNEL=test sudo ./install.sh
  CONTACTSYNC_REF=v3.5.4 sudo ./install.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stable) CHANNEL=stable; shift ;;
    --test|--development|--dev) CHANNEL=test; shift ;;
    --ref) REF="${2:-}"; [[ -n "$REF" ]] || { echo "--ref benötigt einen Wert" >&2; exit 2; }; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Bitte als root ausführen (z. B. sudo ./install.sh --test)." >&2
  exit 1
fi

if [[ -z "$REF" ]]; then
  case "$CHANNEL" in
    stable) REF="$DEFAULT_BRANCH" ;;
    test|development|dev) REF="$TEST_BRANCH" ;;
    *) echo "Unbekannter Kanal: $CHANNEL" >&2; exit 2 ;;
  esac
fi

cleanup() {
  [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]] && rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "ContactSync Professional"
echo "Quelle: GitHub ${REPO}"
echo "Ref:    ${REF}"

apt-get update
apt-get install -y python3 python3-venv python3-pip curl ca-certificates tar

TMP_DIR="$(mktemp -d)"
ARCHIVE="$TMP_DIR/contactsync.tar.gz"
SOURCE="$TMP_DIR/source"
mkdir -p "$SOURCE"

ENCODED_REF="${REF//\//%2F}"
curl -fL --retry 3 --connect-timeout 15 \
  "https://github.com/${REPO}/archive/refs/heads/${ENCODED_REF}.tar.gz" \
  -o "$ARCHIVE" || {
    echo "Branch-Download fehlgeschlagen; versuche Tag/Commit-Archiv ..."
    curl -fL --retry 3 --connect-timeout 15 \
      "https://github.com/${REPO}/archive/${REF}.tar.gz" \
      -o "$ARCHIVE"
  }

tar -xzf "$ARCHIVE" -C "$SOURCE" --strip-components=1
[[ -d "$SOURCE/contactsync" && -f "$SOURCE/pyproject.toml" ]] || {
  echo "Ungültiges ContactSync-Quellarchiv." >&2
  exit 1
}

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Beide Prozesse können dieselbe SQLite-Datenbank verwenden. Für ein konsistentes
# Upgrade werden deshalb Webdienst und Automation-Worker vor der Sicherung gestoppt.
systemctl stop "$AUTOMATION_SERVICE" 2>/dev/null || true
systemctl stop "$MAIN_SERVICE" 2>/dev/null || true
mkdir -p "$DATA_DIR"
if [[ -f "$DB_FILE" ]]; then
  cp -a "$DB_FILE" "$DB_BACKUP"
  echo "Datenbank-Sicherheitskopie: $DB_BACKUP"
fi

# Bestehende Datenbank und Konfiguration unter /var/lib bleiben erhalten.
# Wichtig: Das virtuelle Environment wird erst NACH dem finalen Verschieben
# unter APP_DIR erzeugt. Python-Entry-Points enthalten absolute Shebang-Pfade
# und dürfen deshalb nicht aus APP_DIR.new verschoben werden.
rm -rf "$APP_DIR.new" "$APP_DIR.old"
mkdir -p "$APP_DIR.new"
cp -a "$SOURCE/contactsync" "$SOURCE/pyproject.toml" "$APP_DIR.new/"
[[ -d "$SOURCE/packaging" ]] && cp -a "$SOURCE/packaging" "$APP_DIR.new/"

[[ -f "$APP_DIR.new/packaging/contactsync-professional.service" ]] || {
  echo "Systemd-Service-Datei fehlt im GitHub-Stand." >&2
  exit 1
}
[[ -f "$APP_DIR.new/packaging/contactsync-automation.service" ]] || {
  echo "Automation-Service-Datei fehlt im GitHub-Stand." >&2
  exit 1
}

[[ -d "$APP_DIR" ]] && mv "$APP_DIR" "$APP_DIR.old"
mv "$APP_DIR.new" "$APP_DIR"

rollback() {
  echo "Installation fehlgeschlagen; vorherigen Programmstand wiederherstellen ..." >&2
  systemctl stop "$AUTOMATION_SERVICE" 2>/dev/null || true
  systemctl stop "$MAIN_SERVICE" 2>/dev/null || true
  rm -rf "$APP_DIR"
  if [[ -d "$APP_DIR.old" ]]; then
    mv "$APP_DIR.old" "$APP_DIR"
    [[ -f "$APP_DIR/packaging/contactsync-professional.service" ]] && install -m 0644 "$APP_DIR/packaging/contactsync-professional.service" "/etc/systemd/system/$MAIN_SERVICE"
    [[ -f "$APP_DIR/packaging/contactsync-automation.service" ]] && install -m 0644 "$APP_DIR/packaging/contactsync-automation.service" "/etc/systemd/system/$AUTOMATION_SERVICE"
    systemctl daemon-reload || true
    systemctl restart "$MAIN_SERVICE" || true
    systemctl restart "$AUTOMATION_SERVICE" 2>/dev/null || true
  fi
  if [[ -f "$DB_BACKUP" ]]; then
    echo "Hinweis: Datenbank-Sicherheitskopie bleibt erhalten: $DB_BACKUP" >&2
  fi
}

if ! python3 -m venv "$APP_DIR/venv"; then rollback; exit 1; fi
if ! "$APP_DIR/venv/bin/pip" install --upgrade pip; then rollback; exit 1; fi
if ! "$APP_DIR/venv/bin/pip" install "$APP_DIR"; then rollback; exit 1; fi

# Fail fast if packaging created a broken console entry point.
if ! "$APP_DIR/venv/bin/python" -c "from contactsync.runner import main"; then rollback; exit 1; fi
if [[ "$(head -n 1 "$APP_DIR/venv/bin/contactsync-professional")" != "#!$APP_DIR/venv/bin/"* ]]; then
  echo "Ungültiger Interpreterpfad im ContactSync-Startskript." >&2
  rollback
  exit 1
fi
if [[ "$(head -n 1 "$APP_DIR/venv/bin/contactsync-automation")" != "#!$APP_DIR/venv/bin/"* ]]; then
  echo "Ungültiger Interpreterpfad im ContactSync-Automation-Startskript." >&2
  rollback
  exit 1
fi

install -m 0644 "$APP_DIR/packaging/contactsync-professional.service" "/etc/systemd/system/$MAIN_SERVICE"
install -m 0644 "$APP_DIR/packaging/contactsync-automation.service" "/etc/systemd/system/$AUTOMATION_SERVICE"

chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod 0750 "$DATA_DIR"

systemctl daemon-reload
systemctl enable "$MAIN_SERVICE"
systemctl enable "$AUTOMATION_SERVICE"
if ! systemctl restart "$MAIN_SERVICE"; then rollback; exit 1; fi
if ! systemctl restart "$AUTOMATION_SERVICE"; then rollback; exit 1; fi

for _ in {1..20}; do
  if curl -fsS http://127.0.0.1:8000/health >/tmp/contactsync-health.json 2>/dev/null; then
    rm -rf "$APP_DIR.old"
    echo
    echo "Installation erfolgreich."
    cat /tmp/contactsync-health.json
    echo
    echo "Health-Check: http://127.0.0.1:8000/health"
    [[ -f "$DB_BACKUP" ]] && echo "Upgrade-Backup: $DB_BACKUP"
    [[ "$REF" == "$TEST_BRANCH" ]] && echo "Hinweis: Installiert ist der 3.5.4-Teststand; noch nicht für Produktion freigegeben."
    exit 0
  fi
  sleep 1
done

echo "ContactSync wurde installiert, der Health-Check ist aber fehlgeschlagen." >&2
systemctl --no-pager --full status "$MAIN_SERVICE" || true
journalctl -u "$MAIN_SERVICE" -n 50 --no-pager || true
rollback
exit 1
