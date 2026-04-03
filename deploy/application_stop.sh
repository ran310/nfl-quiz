#!/bin/bash
# CodeDeploy lifecycle: ApplicationStop
set -euo pipefail

systemctl stop nfl-quiz || true
echo "nfl-quiz stopped (or was not running)"
