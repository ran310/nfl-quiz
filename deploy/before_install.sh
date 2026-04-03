#!/bin/bash
# CodeDeploy lifecycle: BeforeInstall — stop this app only, then clean app tree (venv stays).
set -euxo pipefail

systemctl stop nfl-quiz || true

rm -rf /opt/nfl-quiz/app
mkdir -p /opt/nfl-quiz/app
