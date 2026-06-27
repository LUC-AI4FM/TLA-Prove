#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${CHATTLA_HANDOFF_LOG_DIR:-$REPO/outputs/logs}"
INTERVAL="${CHATTLA_HANDOFF_DOCTOR_INTERVAL:-300}"
LABEL="com.chattla.handoff-doctor"
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
    --log-dir)
      LOG_DIR="$2"
      shift
      ;;
    --interval)
      INTERVAL="$2"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/install_handoff_doctor_launchagent.sh [--dry-run] [--repo PATH] [--interval SECONDS]

Install a periodic user LaunchAgent that runs the TLA prover handoff doctor.
The doctor leaves a healthy wait hook alone, reinstalls it if missing, starts
the result watcher after submission, and stops for manual review on hard remote
submission failures.
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

DOCTOR="$REPO/scripts/doctor_tla_prover_handoff.py"
STDOUT="$LOG_DIR/handoff_doctor_launchagent.out.log"
STDERR="$LOG_DIR/handoff_doctor_launchagent.err.log"

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
  <key>StartInterval</key>
  <integer>$INTERVAL</integer>
  <key>WorkingDirectory</key>
  <string>$REPO</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CHATTLA_LOCAL_REPO</key>
    <string>$REPO</string>
    <key>CHATTLA_HANDOFF_LOG_DIR</key>
    <string>$LOG_DIR</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>python3</string>
    <string>$DOCTOR</string>
    <string>--repo</string>
    <string>$REPO</string>
    <string>--live</string>
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
