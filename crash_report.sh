#!/bin/bash
LOG_FILE="/tmp/vcandcpp_fuzzer_logs.txt"
echo "Buttercup Fuzzing - Crash Report"
echo "================================="
echo "Task: a4976051-4b43-4d14-82ca-f628033937c7"
echo ""
echo "Total Crashes: $(grep -c '"crash_count": [1-9]' $LOG_FILE)"
echo ""
echo "By Fuzzer:"
for f in program3_fuzz program3_uaf_fuzz program1_fuzz intoverflow_fuzz; do
    echo "  $f: $(grep "$f" $LOG_FILE | grep -c '"crash_count": [1-9]')"
done
echo ""
echo "Vulnerability Types:"
grep "SUMMARY:" $LOG_FILE | sed 's/.*SUMMARY: //' | sort | uniq -c
