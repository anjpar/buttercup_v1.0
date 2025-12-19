#!/bin/bash
set -e

echo "======================================"
echo "Buttercup Fuzzing - Crash Analysis"
echo "======================================"
echo ""

# Get all logs
echo "[1/6] Fetching logs from all fuzzer pods..."
kubectl -n crs logs -l app=fuzzer-bot --prefix=true > all_fuzzer_logs.txt

# Count crashes
echo "[2/6] Counting crashes..."
total_crashes=$(grep -c '"crash_count": [1-9]' all_fuzzer_logs.txt || echo "0")
echo "Total crashes: $total_crashes"

# Extract by fuzzer
echo "[3/6] Breaking down by fuzzer..."
for fuzzer in program3_fuzz program3_uaf_fuzz program1_fuzz intoverflow_fuzz; do
    count=$(grep "$fuzzer" all_fuzzer_logs.txt | grep -c '"crash_count": [1-9]' || echo "0")
    echo "  $fuzzer: $count"
done

# Extract summaries
echo "[4/6] Extracting crash summaries..."
grep -E "SUMMARY:|artifact_prefix.*crash-" all_fuzzer_logs.txt > crash_summaries.txt

# Extract detailed crashes
echo "[5/6] Extracting detailed crash info..."
grep -B30 '"crash_count": [1-9]' all_fuzzer_logs.txt > crashes_detailed.txt

# Create report
echo "[6/6] Generating report..."
cat > CRASH_REPORT.txt <<REPORT
Buttercup Fuzzing Results
=========================
Task: a4976051-4b43-4d14-82ca-f628033937c7
Total Crashes: $total_crashes

Vulnerability Types:
$(grep "SUMMARY:" all_fuzzer_logs.txt | sed 's/.*SUMMARY: //' | sort | uniq -c)

Details available in:
- all_fuzzer_logs.txt (complete logs)
- crash_summaries.txt (crash summaries)
- crashes_detailed.txt (full crash context)
REPORT

echo ""
echo "✓ Analysis complete!"
echo "✓ Report saved to: CRASH_REPORT.txt"
echo "✓ Detailed logs in: all_fuzzer_logs.txt"
echo "✓ Crash count: $total_crashes"
