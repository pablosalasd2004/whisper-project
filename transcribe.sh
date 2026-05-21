#!/bin/bash
# Voice-to-text toggle: first press starts recording, second press transcribes.
# Uses whisper.cpp with Vulkan backend.

WHISPER_BIN="$HOME/.whisper/whisper.cpp/build/bin/whisper-cli"
MODEL="$HOME/.whisper/whisper.cpp/models/ggml-large-v3.bin"
TMPFILE="/tmp/whisper-recording.wav"
PIDFILE="/tmp/whisper-recording.pid"
STATEFILE="/tmp/whisper-state"
INDICATOR_PIDFILE="/tmp/whisper-indicator.pid"

write_state() { echo "$1" > "$STATEFILE"; }

# ── STOP: already recording → transcribe ────────────────────────────────────
if [[ -f "$PIDFILE" ]]; then
    REC_PID=$(cat "$PIDFILE")
    kill "$REC_PID" 2>/dev/null
    rm -f "$PIDFILE"

    sleep 0.2

    FILESIZE=$(stat -c%s "$TMPFILE" 2>/dev/null || echo 0)
    if [[ "$FILESIZE" -lt 32000 ]]; then
        write_state "done"
        rm -f "$TMPFILE"
        exit 0
    fi

    write_state "transcribing"

    RESULT=$("$WHISPER_BIN" \
        -m "$MODEL" \
        -f "$TMPFILE" \
        -l auto \
        --no-timestamps \
        2>/dev/null \
        | sed '/^\[/d' \
        | sed 's/^[[:space:]]*//' \
        | tr -s '\n' ' ' \
        | sed 's/[[:space:]]*$//')

    rm -f "$TMPFILE"
    write_state "done"

    [[ -z "$RESULT" ]] && exit 0

    echo -n "$RESULT" | wl-copy
    sleep 0.1
    wtype "$RESULT"
    exit 0
fi

# ── START: begin recording ───────────────────────────────────────────────────
write_state "recording"

python3 "$HOME/.whisper/indicator.py" &
echo $! > "$INDICATOR_PIDFILE"

pw-record --channels=1 --rate=16000 --format=s16 "$TMPFILE" &
echo $! > "$PIDFILE"
