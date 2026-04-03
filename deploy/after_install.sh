#!/bin/bash
# CodeDeploy lifecycle: AfterInstall — venv + pip + env file.
set -euxo pipefail

APP_DIR="/opt/nfl-quiz/app"
VENV="/opt/nfl-quiz/venv"

if command -v python3.11 &>/dev/null; then
  PY=python3.11
elif command -v python3 &>/dev/null; then
  PY=python3
else
  echo "ERROR: python3 not found on the host." >&2
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  "${PY}" -m venv "${VENV}"
fi

"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

# Must stay /nfl-quiz to match nginx (ec2-nginx-stack). Wrong or missing value → CSS/JS load from /static on wrong host.
if [[ ! -f /etc/nfl-quiz.env ]]; then
  echo 'APPLICATION_ROOT=/nfl-quiz' > /etc/nfl-quiz.env
elif ! grep -q '^APPLICATION_ROOT=' /etc/nfl-quiz.env 2>/dev/null; then
  echo 'APPLICATION_ROOT=/nfl-quiz' >> /etc/nfl-quiz.env
else
  sed -i 's|^APPLICATION_ROOT=.*|APPLICATION_ROOT=/nfl-quiz|' /etc/nfl-quiz.env
fi
if ! grep -q '^SECRET_KEY=' /etc/nfl-quiz.env 2>/dev/null; then
  echo "SECRET_KEY=$(openssl rand -hex 32)" >> /etc/nfl-quiz.env
fi

echo "AfterInstall complete"
