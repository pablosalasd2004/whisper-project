#!/bin/bash
# Cancela la grabación de Whisper desde cualquier contexto

PIDFILE="/tmp/whisper-recording.pid"
STATEFILE="/tmp/whisper-state"

# Matar pw-record
if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null
    rm -f "$PIDFILE"
fi

# Señalar al indicator que cierre
echo "cancel" > "$STATEFILE"

# Eliminar el binding ESC temporal
hyprctl keyword unbind "n,Escape"

# Limpiar archivos temporales
rm -f /tmp/whisper-recording.wav
