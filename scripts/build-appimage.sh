#!/usr/bin/env bash
# NeXXus — AppImage (Linux x86_64): nexxusd + nexxus-desktop monitor.
# Usage: bash scripts/build-appimage.sh <nexxusd> <nexxus-desktop> [version] [appimagetool]
# appimagetool скачивается автоматически (или передайте путь 4-м аргументом).
set -euo pipefail

NEXXUSD="${1:?path to nexxusd binary}"
DESKTOP="${2:?path to nexxus-desktop binary}"
VERSION="${3:-2.0.0}"
TOOL="${4:-}"
ARCH="x86_64"
OUT="dist/NeXXus-${VERSION}-${ARCH}.AppImage"
APPDIR="dist/AppDir"

if [ -z "$TOOL" ]; then
  TOOL="dist/appimagetool-${ARCH}.AppImage"
  if [ ! -x "$TOOL" ]; then
    echo "downloading appimagetool…"
    curl -fsSL -o "$TOOL" \
      "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-${ARCH}.AppImage"
    chmod +x "$TOOL"
  fi
fi

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps" \
         "$APPDIR/usr/share/metainfo" "$APPDIR/usr/share/nexxus"

install -m 0755 "$NEXXUSD" "$APPDIR/usr/bin/nexxusd"
install -m 0755 "$DESKTOP" "$APPDIR/usr/bin/nexxus-desktop"

# иконка: из репо desktop, иначе заглушка
ICON_SRC="nexxus-desktop/src-tauri/icons/icon-256.png"
[ -f "$ICON_SRC" ] || ICON_SRC="nexxus-desktop/src-tauri/icons/icon.png"
if [ -f "$ICON_SRC" ]; then
  install -m 0644 "$ICON_SRC" "$APPDIR/nexxus.png"
  install -m 0644 "$ICON_SRC" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nexxus.png"
else
  echo "WARN: icon not found, AppImage без иконки" >&2
  : > "$APPDIR/nexxus.png" # placeholder, appimagetool требует файл
fi

cat > "$APPDIR/nexxus.desktop" <<'EOF'
[Desktop Entry]
Name=NeXXus Node Monitor
Comment=P2P storage node monitor (NeXXuS)
Exec=nexxus-desktop
Icon=nexxus
Type=Application
Categories=Network;Utility;
EOF
cp "$APPDIR/nexxus.desktop" "$APPDIR/usr/share/applications/nexxus.desktop"

# AppStream метаданные (appimagetool без них ругается warning-ом)
if [ -f packaging/io.github.perfectfriend.nexxus.appdata.xml ]; then
  install -m 0644 packaging/io.github.perfectfriend.nexxus.appdata.xml "$APPDIR/usr/share/metainfo/io.github.perfectfriend.nexxus.appdata.xml"
fi

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
# AppRun: по умолчанию открываем монитор; nexxusd стартует через guardian/monitor.
HERE="$(dirname "$(readlink -f "${0}")")"
exec "$HERE/usr/bin/nexxus-desktop" "$@"
EOF
chmod +x "$APPDIR/AppRun"

mkdir -p dist
# appimagetool внутри контейнера без FUSE: распаковываем и вызываем --appimage-extract-and-run эквивалент
if [ "${APPIMAGE_EXTRACT_AND_RUN:-0}" = "1" ] || [ ! -e /dev/fuse ]; then
  "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"
else
  "$TOOL" "$APPDIR" "$OUT"
fi
chmod +x "$OUT"
echo "OK: $OUT ($(du -h "$OUT" | cut -f1))"
