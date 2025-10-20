#!/bin/bash
# Launch 10-minute test task
curl -X POST http://127.0.0.1:31323/webhook/trigger_task \
  -H "Content-Type: application/json" \
  -d @tasks/task-lwip-test.json
