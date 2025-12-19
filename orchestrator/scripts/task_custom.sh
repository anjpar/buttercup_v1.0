#!/bin/bash
curl -X 'POST' 'http://127.0.0.1:31323/webhook/trigger_task' -H 'Content-Type: application/json' -d '{
    "challenge_repo_url": "https://github.com/hardik05/Damn_Vulnerable_C_Program.git",
    "challenge_repo_base_ref": "master",
    "challenge_repo_head_ref": "master",
    "fuzz_tooling_url": "https://github.com/anjpar/oss-fuzz",
    "fuzz_tooling_ref": "master",
    "fuzz_tooling_project_name": "dvcp",
    "duration": 1800
}'
