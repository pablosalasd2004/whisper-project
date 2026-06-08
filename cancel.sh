#!/bin/bash
# Cancel an active Whisper recording from any context (e.g. ESC key in the HUD).

PIDFILE="${WHISPER_PIDFILE:-/tmp/whisper-recording.pid}"
STATEFILE="${WHISPER_STATEFILE:-/tmp/whisper-state}"

# Signal the indicator to close
echo "cancel" > "$STATEFILE"

# Stop pw-record
if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    rm -f "$PIDFILE"
fi

# Remove temp audio file
rm -f /tmp/whisper-recording.wav
