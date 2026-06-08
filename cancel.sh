#!/bin/bash
# Cancela la grabación de Whisper desde cualquier contexto

PIDFILE="${WHISPER_PIDFILE:-/tmp/whisper-recording.pid}"
STATEFILE="${WHISPER_STATEFILE:-/tmp/whisper-state}"

# Señalar al indicator que cierre
echo "cancel" > "$STATEFILE"

# Matar pw-record
if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    rm -f "$PIDFILE"
fi

# Limpiar archivos temporales
rm -f /tmp/whisper-recording.wav
