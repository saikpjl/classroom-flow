#!/usr/bin/env zsh
# Instala o agendamento (a cada 30 min) no launchd do macOS.
set -euo pipefail
PROJECT_DIR="${0:A:h:h}"
PLIST="$HOME/Library/LaunchAgents/com.classroomflow.monitor.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" -e "s|__HOME__|$HOME|g" \
    "$PROJECT_DIR/launchd/com.classroomflow.monitor.plist" > "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "✓ Agendado. Logs: ~/Library/Logs/classroomflow.log"
echo "  Para remover: launchctl bootout gui/$(id -u) $PLIST && rm $PLIST"
