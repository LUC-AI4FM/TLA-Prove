#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
fi

REPO="${CHATTLA_REPO:-$HOME/GitHub/ChatTLA/ChatTLA}"
CODEX_BIN="${CODEX_BIN:-$HOME/.local/bin/codex}"
SOPHIA_CTL="${SOPHIA_CTL:-$HOME/.ssh/codex-sophia-ctl}"
AGENT_DIR="$HOME/Library/LaunchAgents"
SUPERVISOR_PLIST="$AGENT_DIR/com.chattla.codex-goal-supervisor.plist"
AUTOPILOT_PLIST="$AGENT_DIR/com.chattla.tla-prover-autopilot.plist"

write_plist() {
  local path="$1"
  local label="$2"
  local program="$3"
  cat > "$path" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CHATTLA_REPO</key>
    <string>$REPO</string>
    <key>CODEX_BIN</key>
    <string>$CODEX_BIN</string>
    <key>SOPHIA_CTL</key>
    <string>$SOPHIA_CTL</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd "$REPO" &amp;&amp; exec "$program"</string>
  </array>
  <key>StandardOutPath</key>
  <string>$REPO/outputs/logs/$label.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$REPO/outputs/logs/$label.launchd.err.log</string>
</dict>
</plist>
PLIST
}

if [ "$DRY_RUN" = "1" ]; then
  cat <<EOF
Would install:
  $SUPERVISOR_PLIST -> $REPO/scripts/macmini_codex_goal_supervisor.sh
  $AUTOPILOT_PLIST -> $REPO/scripts/macmini_tla_prover_autopilot.sh
Would run:
  launchctl bootstrap gui/$(id -u) "$SUPERVISOR_PLIST"
  launchctl bootstrap gui/$(id -u) "$AUTOPILOT_PLIST"
EOF
  exit 0
fi

[ -d "$REPO" ] || { echo "repo missing: $REPO" >&2; exit 1; }
[ -x "$REPO/scripts/macmini_codex_goal_supervisor.sh" ] || { echo "missing supervisor script" >&2; exit 1; }
[ -x "$REPO/scripts/macmini_tla_prover_autopilot.sh" ] || { echo "missing autopilot script" >&2; exit 1; }
mkdir -p "$AGENT_DIR" "$REPO/outputs/logs"

write_plist "$SUPERVISOR_PLIST" \
  "com.chattla.codex-goal-supervisor" \
  "$REPO/scripts/macmini_codex_goal_supervisor.sh"
write_plist "$AUTOPILOT_PLIST" \
  "com.chattla.tla-prover-autopilot" \
  "$REPO/scripts/macmini_tla_prover_autopilot.sh"

launchctl bootout "gui/$(id -u)" "$SUPERVISOR_PLIST" >/dev/null 2>&1 || true
launchctl bootout "gui/$(id -u)" "$AUTOPILOT_PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$SUPERVISOR_PLIST"
launchctl bootstrap "gui/$(id -u)" "$AUTOPILOT_PLIST"
launchctl kickstart -k "gui/$(id -u)/com.chattla.codex-goal-supervisor"
launchctl kickstart -k "gui/$(id -u)/com.chattla.tla-prover-autopilot"

echo "installed LaunchAgents:"
echo "  $SUPERVISOR_PLIST"
echo "  $AUTOPILOT_PLIST"
