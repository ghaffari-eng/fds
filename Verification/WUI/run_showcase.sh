#!/bin/bash
# Run all 5 showcase cases with MPI (4 processes)
# Usage: chmod +x run_showcase.sh && ./run_showcase.sh

FDS=~/firemodels/fds/Build/ompi_gnu_linux/fds_ompi_gnu_linux
cd ~/firemodels/fds/Verification/WUI

for CASE in sgs_showcase_none sgs_showcase_rw sgs_showcase_lv sgs_showcase_df sgs_showcase_lv_inert; do
    echo "============================================"
    echo "Running: ${CASE}"
    echo "Started: $(date)"
    echo "============================================"

    START=$(date +%s)
    mpiexec -np 4 $FDS ${CASE}.fds > ${CASE}.log 2>&1
    END=$(date +%s)
    ELAPSED=$((END - START))

    # Check for errors
    ERR_COUNT=0
    for errfile in ${CASE}*.err; do
        if [ -f "$errfile" ] && [ -s "$errfile" ]; then
            ERR_COUNT=$((ERR_COUNT + 1))
        fi
    done

    if [ $ERR_COUNT -gt 0 ]; then
        echo "  ERRORS DETECTED ($ERR_COUNT .err files with content)"
    else
        echo "  Completed OK (${ELAPSED}s = $((ELAPSED/60))m)"
    fi
    echo ""
done

echo "============================================"
echo "All 5 showcase cases complete!"
echo "============================================"

# Collect results
mkdir -p ~/showcase_results
cp sgs_showcase_*_devc.csv ~/showcase_results/ 2>/dev/null
cp sgs_showcase_*.err ~/showcase_results/ 2>/dev/null
cp sgs_showcase_*.log ~/showcase_results/ 2>/dev/null
cd ~ && tar czf showcase_results.tar.gz showcase_results/
echo "Results zipped to ~/showcase_results.tar.gz"
