#!/bin/bash
# Tests for transcribe.sh and cancel.sh
# Uses a temporary directory, mock binaries, and env var overrides so no real
# hardware (microphone, whisper-cli, wtype, …) is needed.

set -euo pipefail

# ---------------------------------------------------------------------------
# Setup: temporary workspace
# ---------------------------------------------------------------------------
TESTDIR=$(mktemp -d)
trap 'rm -rf "$TESTDIR"' EXIT

MOCK_BIN="$TESTDIR/bin"
mkdir -p "$MOCK_BIN"

SCRIPTS_DIR="/tmp/whisper-review"

# Patched copies of the scripts (we use sed to rewrite the WHISPER_BIN path so
# it resolves inside our test tree; everything else is handled via env vars).
TRANSCRIBE="$TESTDIR/transcribe.sh"
CANCEL="$TESTDIR/cancel.sh"

sed "s|WHISPER_DIR:-\$HOME/.whisper|WHISPER_DIR:-$TESTDIR/whisper|g" \
    "$SCRIPTS_DIR/transcribe.sh" > "$TRANSCRIBE"
cp "$SCRIPTS_DIR/cancel.sh" "$CANCEL"
chmod +x "$TRANSCRIBE" "$CANCEL"

# Env vars that override temp file paths
export WHISPER_STATEFILE="$TESTDIR/whisper-state"
export WHISPER_PIDFILE="$TESTDIR/whisper-recording.pid"

# Fake whisper installation tree
FAKE_WHISPER="$TESTDIR/whisper"
mkdir -p "$FAKE_WHISPER/whisper.cpp/build/bin"
mkdir -p "$FAKE_WHISPER/whisper.cpp/models"

# ---------------------------------------------------------------------------
# Mock binaries — all are silent no-ops unless noted otherwise
# ---------------------------------------------------------------------------
make_mock() {
    local name="$1"; shift
    local body="${1:-exit 0}"
    printf '#!/bin/bash\n%s\n' "$body" > "$MOCK_BIN/$name"
    chmod +x "$MOCK_BIN/$name"
}

make_mock pw-record 'while true; do sleep 60; done'   # stays alive like the real one
make_mock wl-copy   'exit 0'
make_mock wtype     'exit 0'
make_mock python3   'exit 0'

# whisper-cli mock: just prints a fixed transcription to stdout
make_mock whisper-cli 'echo "hello world"'

# Also place whisper-cli where transcribe.sh expects it
cp "$MOCK_BIN/whisper-cli" "$FAKE_WHISPER/whisper.cpp/build/bin/whisper-cli"

# Fake model file (just needs to exist)
touch "$FAKE_WHISPER/whisper.cpp/models/ggml-small.bin"

# Prepend mock bin dir to PATH so pw-record, wl-copy, wtype, python3 resolve
export PATH="$MOCK_BIN:$PATH"
export WHISPER_DIR="$FAKE_WHISPER"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
PASS=0
FAIL=0

ok() {
    echo "  PASS: $1"
    PASS=$((PASS + 1))
}

fail() {
    echo "  FAIL: $1"
    echo "        $2"
    FAIL=$((FAIL + 1))
}

assert_file_contains() {
    local label="$1" file="$2" expected="$3"
    local actual
    actual=$(cat "$file" 2>/dev/null || echo "")
    if [[ "$actual" == "$expected" ]]; then
        ok "$label"
    else
        fail "$label" "expected='$expected' actual='$actual'"
    fi
}

assert_file_missing() {
    local label="$1" file="$2"
    if [[ ! -f "$file" ]]; then
        ok "$label"
    else
        fail "$label" "file exists but should be gone: $file"
    fi
}

assert_file_exists() {
    local label="$1" file="$2"
    if [[ -f "$file" ]]; then
        ok "$label"
    else
        fail "$label" "file missing: $file"
    fi
}

# ---------------------------------------------------------------------------
# Test 1: First press — no PIDFILE → should create PIDFILE and write "recording"
# ---------------------------------------------------------------------------
echo "--- Test 1: first press (START)"

rm -f "$WHISPER_STATEFILE" "$WHISPER_PIDFILE"

bash "$TRANSCRIBE" &
SCRIPT_PID=$!
sleep 0.3   # let the script reach the pw-record launch

assert_file_contains "state == recording"  "$WHISPER_STATEFILE" "recording"
assert_file_exists   "PIDFILE created"     "$WHISPER_PIDFILE"

# Clean up: kill pw-record and the script
kill "$(cat "$WHISPER_PIDFILE" 2>/dev/null)" 2>/dev/null || true
wait "$SCRIPT_PID" 2>/dev/null || true
rm -f "$WHISPER_STATEFILE" "$WHISPER_PIDFILE"

# ---------------------------------------------------------------------------
# Test 2: Second press — PIDFILE exists → should write "done" and remove PIDFILE
# ---------------------------------------------------------------------------
echo "--- Test 2: second press (STOP + transcribe)"

# Simulate a previously started recording: place a background sleep as the
# "pw-record" process and write its PID.
sleep 60 &
FAKE_REC_PID=$!
echo "$FAKE_REC_PID" > "$WHISPER_PIDFILE"

# Create a minimal WAV-like file that passes the size check (>32000 bytes)
dd if=/dev/zero bs=1 count=33000 of=/tmp/whisper-recording.wav 2>/dev/null

bash "$TRANSCRIBE"

assert_file_contains "state == done after transcribe"  "$WHISPER_STATEFILE" "done"
assert_file_missing  "PIDFILE removed after transcribe" "$WHISPER_PIDFILE"

# Ensure fake recorder is gone
kill "$FAKE_REC_PID" 2>/dev/null || true
rm -f /tmp/whisper-recording.wav "$WHISPER_STATEFILE"

# ---------------------------------------------------------------------------
# Test 3: Dep check — whisper-cli absent → write "done" and exit 1
# ---------------------------------------------------------------------------
echo "--- Test 3: dep check — whisper-cli absent"

rm -f "$WHISPER_STATEFILE" "$WHISPER_PIDFILE"

# Hide the mock whisper-cli from PATH and remove the binary from the fake tree
ORIG_PATH="$PATH"
export PATH="$MOCK_BIN:$PATH"
chmod -x "$FAKE_WHISPER/whisper.cpp/build/bin/whisper-cli"
mv "$MOCK_BIN/whisper-cli" "$MOCK_BIN/whisper-cli.bak"

bash "$TRANSCRIBE" || true

assert_file_contains "state == done when whisper-cli missing" \
    "$WHISPER_STATEFILE" "done"
assert_file_missing  "PIDFILE not created on dep failure" "$WHISPER_PIDFILE"

# Restore
mv "$MOCK_BIN/whisper-cli.bak" "$MOCK_BIN/whisper-cli"
chmod +x "$FAKE_WHISPER/whisper.cpp/build/bin/whisper-cli"
export PATH="$ORIG_PATH"
rm -f "$WHISPER_STATEFILE"

# ---------------------------------------------------------------------------
# Test 4: Dep check — model absent → write "done" and exit 1
# ---------------------------------------------------------------------------
echo "--- Test 4: dep check — model absent"

rm -f "$WHISPER_STATEFILE" "$WHISPER_PIDFILE"

mv "$FAKE_WHISPER/whisper.cpp/models/ggml-small.bin" \
   "$FAKE_WHISPER/whisper.cpp/models/ggml-small.bin.bak"

bash "$TRANSCRIBE" || true

assert_file_contains "state == done when model missing" \
    "$WHISPER_STATEFILE" "done"
assert_file_missing  "PIDFILE not created on dep failure" "$WHISPER_PIDFILE"

# Restore
mv "$FAKE_WHISPER/whisper.cpp/models/ggml-small.bin.bak" \
   "$FAKE_WHISPER/whisper.cpp/models/ggml-small.bin"
rm -f "$WHISPER_STATEFILE"

# ---------------------------------------------------------------------------
# Test 5: cancel.sh — writes "cancel", kills the PIDFILE process, removes PIDFILE
# ---------------------------------------------------------------------------
echo "--- Test 5: cancel.sh"

sleep 60 &
FAKE_REC_PID=$!
echo "$FAKE_REC_PID" > "$WHISPER_PIDFILE"

bash "$CANCEL"

assert_file_contains "state == cancel" "$WHISPER_STATEFILE" "cancel"
assert_file_missing  "PIDFILE removed by cancel" "$WHISPER_PIDFILE"

# The fake process should no longer be alive
sleep 0.1
if kill -0 "$FAKE_REC_PID" 2>/dev/null; then
    fail "fake pw-record killed by cancel" "process $FAKE_REC_PID still alive"
    kill "$FAKE_REC_PID" 2>/dev/null || true
else
    ok "fake pw-record killed by cancel"
fi

rm -f "$WHISPER_STATEFILE"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
