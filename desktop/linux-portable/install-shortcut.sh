#!/usr/bin/env bash
# Create desktop/menu shortcuts with absolute paths (run once after unzip).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

write_desktop() {
  local target="$1"
  cat > "$target" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Анализ работы отделения
Comment=Анализ ЭМК, КСГ, операций
Exec=$ROOT/start.sh
Path=$ROOT
Icon=$ROOT/icon.png
Terminal=false
Categories=Office;
StartupNotify=true
EOF
  chmod +x "$target"
}

created=0
for desktop_dir in "$HOME/Desktop" "$HOME/Рабочий стол" "$HOME/desktop"; do
  if [[ -d "$desktop_dir" ]]; then
    write_desktop "$desktop_dir/AnalizIstorii.desktop"
    echo "Ярлык на рабочем столе: $desktop_dir/AnalizIstorii.desktop"
    created=1
  fi
done

mkdir -p "$HOME/.local/share/applications"
write_desktop "$HOME/.local/share/applications/AnalizIstorii.desktop"
echo "Пункт в меню приложений: ~/.local/share/applications/AnalizIstorii.desktop"

if [[ "$created" -eq 0 ]]; then
  echo "Папка рабочего стола не найдена — используйте ярлык в папке программы: $ROOT/AnalizIstorii.desktop"
fi
