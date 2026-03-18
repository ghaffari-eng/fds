#!/bin/bash
# Run ember ignition heat transfer verification tests
set -e

FDS=~/firemodels/fds/Build/ompi_gnu_linux/fds_ompi_gnu_linux
TESTDIR=~/firemodels/fds/Verification/WUI

echo "=== Ember Ignition Heat Transfer Verification ==="
echo ""

# Check binary exists
if [ ! -x "$FDS" ]; then
   echo "ERROR: FDS binary not found at $FDS"
   exit 1
fi

# Run test 1: ember with heat transfer enabled
echo "--- Running ember_ignition_ht (EMBER_HEAT_TRANSFER=.TRUE.) ---"
cd "$TESTDIR"
$FDS ember_ignition_ht.fds 2> ember_ignition_ht.err
if grep -q "forrtl" ember_ignition_ht.err 2>/dev/null; then
   echo "ERROR: Fortran runtime error in ember_ignition_ht"
   cat ember_ignition_ht.err
   exit 1
else
   echo "PASS: No forrtl errors"
fi

# Run test 2: ember without heat transfer (backward compatibility)
echo ""
echo "--- Running ember_ignition_ht_off (default, no ember heat transfer) ---"
$FDS ember_ignition_ht_off.fds 2> ember_ignition_ht_off.err
if grep -q "forrtl" ember_ignition_ht_off.err 2>/dev/null; then
   echo "ERROR: Fortran runtime error in ember_ignition_ht_off"
   cat ember_ignition_ht_off.err
   exit 1
else
   echo "PASS: No forrtl errors"
fi

# Print surface temperature results
echo ""
echo "=== Surface Temperature Results ==="
echo ""
echo "--- ember_ignition_ht (heat transfer ON) ---"
if [ -f ember_ignition_ht_devc.csv ]; then
   head -2 ember_ignition_ht_devc.csv
   echo "..."
   tail -5 ember_ignition_ht_devc.csv
else
   echo "WARNING: ember_ignition_ht_devc.csv not found"
fi

echo ""
echo "--- ember_ignition_ht_off (heat transfer OFF) ---"
if [ -f ember_ignition_ht_off_devc.csv ]; then
   head -2 ember_ignition_ht_off_devc.csv
   echo "..."
   tail -5 ember_ignition_ht_off_devc.csv
else
   echo "WARNING: ember_ignition_ht_off_devc.csv not found"
fi

# Compare final temperatures
echo ""
echo "=== Comparison ==="
if [ -f ember_ignition_ht_devc.csv ] && [ -f ember_ignition_ht_off_devc.csv ]; then
   T_HT=$(tail -1 ember_ignition_ht_devc.csv | cut -d',' -f2)
   T_OFF=$(tail -1 ember_ignition_ht_off_devc.csv | cut -d',' -f2)
   echo "Final floor temp (HT on):  $T_HT C"
   echo "Final floor temp (HT off): $T_OFF C"
fi

echo ""
echo "=== Tests Complete ==="
