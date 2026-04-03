#!/bin/bash
# CodeDeploy lifecycle: BeforeInstall — clean app tree (venv stays under /opt/nfl-quiz/venv).
set -euxo pipefail

rm -rf /opt/nfl-quiz/app
mkdir -p /opt/nfl-quiz/app
