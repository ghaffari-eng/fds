#!/bin/bash
# Run SGS turbulent dispersion test cases
# Usage: ./run_sgs_turb_tests.sh tier1|tier2 [--parallel N]

set -euo pipefail

FDS_BIN="${FDS_BIN:-$HOME/firemodels/fds/Build/ompi_gnu_linux/fds_ompi_gnu_linux}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 tier1|tier2"
    echo "  tier1: Run 1m resolution cases (10 cases, ~2-5 min each)"
    echo "  tier2: Run 0.5m resolution cases (10 cases, ~10-30 min each)"
    exit 1
fi

TIER="$1"

case "$TIER" in
    tier1) SUFFIX="_1m" ;;
    tier2) SUFFIX="_0p5m" ;;
    *)
        echo "Error: Unknown tier '$TIER'. Use tier1 or tier2."
        exit 1
        ;;
esac

# Check FDS binary exists
if [ ! -x "$FDS_BIN" ]; then
    echo "Error: FDS binary not found at $FDS_BIN"
    echo "Set FDS_BIN environment variable or build FDS first."
    exit 1
fi

# Collect matching cases
CASES=()
for f in "$SCRIPT_DIR"/sgs_turb_*${SUFFIX}.fds; do
    [ -f "$f" ] && CASES+=("$f")
done

if [ ${#CASES[@]} -eq 0 ]; then
    echo "Error: No sgs_turb_*${SUFFIX}.fds files found in $SCRIPT_DIR"
    exit 1
fi

echo "=========================================="
echo " SGS Turbulent Dispersion Tests — ${TIER}"
echo "=========================================="
echo "FDS binary: $FDS_BIN"
echo "Cases: ${#CASES[@]}"
echo ""

PASSED=0
FAILED=0
ERRORS=()

for fds_file in "${CASES[@]}"; do
    CASE_NAME="$(basename "$fds_file" .fds)"
    echo "--- Running: $CASE_NAME ---"

    cd "$SCRIPT_DIR"

    # Run FDS (single MPI rank for these small cases)
    START_TIME=$SECONDS
    if "$FDS_BIN" "$fds_file" > "${CASE_NAME}.log" 2>&1; then
        ELAPSED=$(( SECONDS - START_TIME ))
        echo "  Completed in ${ELAPSED}s"
    else
        ELAPSED=$(( SECONDS - START_TIME ))
        echo "  FDS exited with error after ${ELAPSED}s"
    fi

    # Check for Fortran runtime errors
    ERR_FILE="${CASE_NAME}.err"
    if [ -f "$ERR_FILE" ] && grep -qi 'forrtl\|STOP\|error' "$ERR_FILE" 2>/dev/null; then
        echo "  *** ERROR detected in $ERR_FILE ***"
        grep -i 'forrtl\|STOP\|error' "$ERR_FILE" | head -5
        FAILED=$((FAILED + 1))
        ERRORS+=("$CASE_NAME")
    else
        echo "  OK"
        PASSED=$((PASSED + 1))
    fi
    echo ""
done

echo "=========================================="
echo " Summary"
echo "=========================================="
echo "Passed: $PASSED / ${#CASES[@]}"
echo "Failed: $FAILED / ${#CASES[@]}"
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo "Failed cases:"
    for e in "${ERRORS[@]}"; do
        echo "  - $e"
    done
fi
echo "=========================================="
