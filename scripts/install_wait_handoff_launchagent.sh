#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAC_HOST="${CHATTLA_MAC_HOST:-ericspencer@erics-mac-mini.local}"
MAC_KEY="${CHATTLA_MAC_KEY:-$HOME/.ssh/id_ed25519_mac_mini}"
RELAY_HOST="${CHATTLA_RELAY_HOST:-$MAC_HOST}"
RELAY_KEY="${CHATTLA_RELAY_KEY:-$MAC_KEY}"
RELAY_LABEL="${CHATTLA_RELAY_LABEL:-Mac mini}"
LOG_DIR="${CHATTLA_HANDOFF_LOG_DIR:-$REPO/outputs/logs}"
SLEEP_SECONDS="${CHATTLA_MACMINI_WAIT_SLEEP:-60}"
MAX_ATTEMPTS="${CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS:-0}"
LABEL="com.chattla.wait-for-macmini-handoff"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --repo)
      REPO="$2"
      LOG_DIR="${CHATTLA_HANDOFF_LOG_DIR:-$REPO/outputs/logs}"
      shift
      ;;
    --mac-host)
      MAC_HOST="$2"
      RELAY_HOST="${CHATTLA_RELAY_HOST:-$MAC_HOST}"
      shift
      ;;
    --mac-key)
      MAC_KEY="$2"
      RELAY_KEY="${CHATTLA_RELAY_KEY:-$MAC_KEY}"
      shift
      ;;
    --relay-host)
      RELAY_HOST="$2"
      MAC_HOST="$2"
      shift
      ;;
    --relay-key)
      RELAY_KEY="$2"
      MAC_KEY="$2"
      shift
      ;;
    --relay-label)
      RELAY_LABEL="$2"
      shift
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift
      ;;
    --sleep-seconds)
      SLEEP_SECONDS="$2"
      shift
      ;;
    --max-attempts)
      MAX_ATTEMPTS="$2"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/install_wait_handoff_launchagent.sh [--dry-run] [--repo PATH] [--mac-host USER@HOST] [--relay-host USER@HOST]

Install a one-shot user LaunchAgent that waits for the relay host to become SSH
reachable, then runs scripts/wait_for_macmini_and_handoff_known18.sh
--submit-sft-preflight. KeepAlive is false so successful launch does not repeat.
EOF
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

WRAPPER="$REPO/scripts/wait_for_macmini_and_handoff_known18.sh"
STDOUT="$LOG_DIR/wait_for_macmini_launchagent.out.log"
STDERR="$LOG_DIR/wait_for_macmini_launchagent.err.log"

write_plist() {
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CHATTLA_LOCAL_REPO</key>
    <string>$REPO</string>
    <key>CHATTLA_MAC_HOST</key>
    <string>$MAC_HOST</string>
    <key>CHATTLA_MAC_KEY</key>
    <string>$MAC_KEY</string>
    <key>CHATTLA_RELAY_HOST</key>
    <string>$RELAY_HOST</string>
    <key>CHATTLA_RELAY_KEY</key>
    <string>$RELAY_KEY</string>
    <key>CHATTLA_RELAY_LABEL</key>
    <string>$RELAY_LABEL</string>
    <key>CHATTLA_HANDOFF_LOG_DIR</key>
    <string>$LOG_DIR</string>
    <key>CHATTLA_MACMINI_WAIT_SLEEP</key>
    <string>$SLEEP_SECONDS</string>
    <key>CHATTLA_MACMINI_WAIT_MAX_ATTEMPTS</key>
    <string>$MAX_ATTEMPTS</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$WRAPPER</string>
    <string>--submit-sft-preflight</string>
  </array>
  <key>StandardOutPath</key>
  <string>$STDOUT</string>
  <key>StandardErrorPath</key>
  <string>$STDERR</string>
</dict>
</plist>
EOF
}

if [ "$DRY_RUN" = "1" ]; then
  echo "$PLIST"
  write_plist
  exit 0
fi

mkdir -p "$(dirname "$PLIST")" "$LOG_DIR"
write_plist > "$PLIST"
launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/$LABEL"
echo "installed $PLIST"
