#!/bin/bash
# Kill all pods related to a task

if [ -z "$1" ]; then
    echo "Usage: ./kill-task.sh <task-id>"
    echo "Example: ./kill-task.sh 42663b10-2409-483f-be06-81c510262a18"
    exit 1
fi

TASK_ID=$1

echo "Killing task: $TASK_ID"

# Delete pods with this task-id label
kubectl delete pods -n crs -l task-id=$TASK_ID

# Also delete any pods with the task id in the name
kubectl get pods -n crs | grep $TASK_ID | awk '{print $1}' | xargs -r kubectl delete pod -n crs

echo "Task $TASK_ID terminated"
