#!/bin/bash
# List all running fuzzing tasks

echo "=== Running Fuzzing Pods ==="
kubectl get pods -n crs | grep -E "NAME|fuzz|build" | grep -v "NAMESPACE"

echo ""
echo "=== Recent Task Events ==="
kubectl get events -n crs --sort-by='.lastTimestamp' | tail -10
