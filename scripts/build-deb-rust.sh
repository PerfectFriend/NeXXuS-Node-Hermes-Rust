#!/usr/bin/env bash
# NeXXus RC1 — Debian package with the RUST daemon + desktop monitor.
# Usage: bash scripts/build-deb-rust.sh <nexxusd> <nexxus-desktop> [version]
set -euo pipefail

NEXXUSD="${1:?path to nexxusd binary}"
DESKTOP="${2:?path to nexxus-desktop binary}"
VERSION="${3:-2.0.0}"
PKG="nexxus"
ARCH="amd64"
STAGE="dist/pkg-staging/${PKG}_${VERSION}_${ARCH}"
DEB="dist/${PKG}_${VERSION}_${ARCH}.deb"

rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/lib/systemd/user" \
         "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/256x256/apps"

install -m 0755 "$NEXXUSD" "$STAGE/usr/bin/nexxusd"
install -m 0755 "$DESKTOP" "$STAGE/usr/bin/nexxus-desktop"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Maintainer: NeXXus <ops@nexxus.local>
Description: NeXXus node daemon (Rust) + desktop monitor (Tauri)
 P2P storage node with encrypted store, BIP39 identity, Tor support,
 and a tray monitor dashboard.
EOF

cat > "$STAGE/usr/lib/systemd/user/nexxus-node.service" <<'EOF'
[Unit]
Description=NeXXus node daemon
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/nexxusd %h/.nexxus/store.redb
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

cat > "$STAGE/usr/lib/systemd/user/nexxus-monitor.service" <<'EOF'
[Unit]
Description=NeXXus desktop monitor
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/nexxus-desktop
Restart=on-failure
RestartSec=5
KillMode=process

[Install]
WantedBy=default.target
EOF

cat > "$STAGE/usr/share/applications/nexxus-monitor.desktop" <<'EOF'
[Desktop Entry]
Name=NeXXus Monitor
Comment=NeXXus node tray monitor
Exec=/usr/bin/nexxus-desktop
Icon=nexxus-monitor
Type=Application
Categories=Network;
EOF

# Tray icon: red N on blue heptagon, transparent bg (per spec).
if [ -f nexxus-desktop/src-tauri/icons/icon.png ]; then
  install -m 0644 nexxus-desktop/src-tauri/icons/icon.png \
    "$STAGE/usr/share/icons/hicolor/256x256/apps/nexxus-monitor.png"
fi

mkdir -p dist
dpkg-deb --build "$STAGE" "$DEB"
echo "✅ built $DEB"
ls -lh "$DEB"
