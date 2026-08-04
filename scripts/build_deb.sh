#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VERSION=$(tr -d '[:space:]' < "$ROOT/version.txt")
OUT="$ROOT/dist/contactsync-professional_${VERSION}_all.deb"
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
PKG="$BUILD/pkg"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/contactsync-professional" "$PKG/etc/systemd/system" "$ROOT/dist"
cp -a "$ROOT/contactsync" "$ROOT/pyproject.toml" "$ROOT/README.md" "$ROOT/version.txt" "$ROOT/projekt.yaml" "$PKG/opt/contactsync-professional/"
cp "$ROOT/debian/control" "$PKG/DEBIAN/control"
sed -i "s/^Version:.*/Version: $VERSION/" "$PKG/DEBIAN/control"
install -m 0755 "$ROOT/debian/postinst" "$PKG/DEBIAN/postinst"
install -m 0755 "$ROOT/debian/prerm" "$PKG/DEBIAN/prerm"
install -m 0644 "$ROOT/packaging/contactsync-professional.service" "$PKG/etc/systemd/system/contactsync-professional.service"
dpkg-deb --root-owner-group --build "$PKG" "$OUT"
sha256sum "$OUT" > "$OUT.sha256"
dpkg-deb -f "$OUT" Package Version Architecture
echo "$OUT"
