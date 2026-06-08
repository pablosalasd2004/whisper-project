#!/bin/bash
# Voice-to-text toggle: first press starts recording, second press transcribes.
# Uses whisper.cpp (build with Vulkan/CUDA/CPU support at compile time).

WHISPER_DIR="${WHISPER_DIR:-$HOME/.whisper}"
WHISPER_MODEL="${WHISPER_MODEL:-ggml-small.bin}"

# Speed tuning — override any of these in your shell profile or keybind
WHISPER_THREADS="${WHISPER_THREADS:-$(nproc)}"  # CPU threads; defaults to all cores
WHISPER_BEAM="${WHISPER_BEAM:-1}"               # 1 = greedy (fastest); 5 = beam search (more accurate)
WHISPER_LANG="${WHISPER_LANG:-auto}"            # set your language code (e.g. "en") to skip detection

# Resolve whisper-cli: prefer the local build, fall back to system PATH
_DEFAULT_BIN="$WHISPER_DIR/whisper.cpp/build/bin/whisper-cli"
if [[ -x "$_DEFAULT_BIN" ]]; then
    WHISPER_BIN="$_DEFAULT_BIN"
elif command -v whisper-cli &>/dev/null; then
    WHISPER_BIN="$(command -v whisper-cli)"
else
    WHISPER_BIN="$_DEFAULT_BIN"   # will fail dep check below with a clear error
fi
MODEL="$WHISPER_DIR/whisper.cpp/models/$WHISPER_MODEL"
TMPFILE="/tmp/whisper-recording.wav"
PIDFILE="${WHISPER_PIDFILE:-/tmp/whisper-recording.pid}"
STATEFILE="${WHISPER_STATEFILE:-/tmp/whisper-state}"
INDICATOR_PIDFILE="${WHISPER_INDICATOR_PIDFILE:-/tmp/whisper-indicator.pid}"
LOGFILE="/tmp/whisper.log"

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
        -l "$WHISPER_LANG" \
        -t "$WHISPER_THREADS" \
        --beam-size "$WHISPER_BEAM" \
        --no-timestamps \
        2>>"$LOGFILE" \
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

check_deps() {
    local ok=1

    if [[ ! -x "$WHISPER_BIN" ]]; then
        echo "$(date): ERROR: whisper-cli not found (checked PATH and $_DEFAULT_BIN)" >> "$LOGFILE"
        ok=0
    fi

    if [[ ! -f "$MODEL" ]]; then
        echo "$(date): ERROR: model not found: $MODEL" >> "$LOGFILE"
        ok=0
    fi

    for cmd in pw-record wl-copy wtype python3; do
        if ! command -v "$cmd" &>/dev/null; then
            echo "$(date): ERROR: missing dependency: $cmd" >> "$LOGFILE"
            ok=0
        fi
    done

    echo "$ok"
}

if [[ "$(check_deps)" != "1" ]]; then
    write_state "done"
    exit 1
fi

write_state "recording"

python3 "$WHISPER_DIR/indicator.py" &
echo $! > "$INDICATOR_PIDFILE"

pw-record --channels=1 --rate=16000 --format=s16 "$TMPFILE" &
echo $! > "$PIDFILE"

# Give PipeWire time to wake the suspended device and route the stream.
# Without this, pw-record may start writing silence while the device is
# still powering on, causing the noise-floor calibration to read zero.
sleep 0.4
