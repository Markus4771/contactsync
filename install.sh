#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Bitte als root ausführen: sudo ./install.sh" >&2
  exit 1
fi

APP_DIR=/opt/contactsync-professional
DATA_DIR=/var/lib/contactsync-professional
SERVICE_USER=contactsync

apt-get update
apt-get install -y python3 python3-venv python3-pip

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

mkdir -p "$APP_DIR" "$DATA_DIR"
cp -a contactsync pyproject.toml "$APP_DIR"/
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install "$APP_DIR"

install -m 0644 packaging/contactsync-professional.service /etc/systemd/system/contactsync-professional.service
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod 0750 "$DATA_DIR"

systemctl daemon-reload
systemctl enable --now contactsync-professional.service

echo "ContactSync Professional 3.3.0 wurde installiert."
echo "Health-Check: curl http://127.0.0.1:8000/health"
