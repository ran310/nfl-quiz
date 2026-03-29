#!/bin/bash
# Run on the EC2 nginx host (via SSM). Args: <s3-bucket> <s3-key>
set -euxo pipefail

BUCKET="$1"
KEY="$2"
APP_DIR="/opt/nfl-quiz/app"
VENV="/opt/nfl-quiz/venv"
TMP="/tmp/nfl-quiz-install-$$"

cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP"
aws s3 cp "s3://${BUCKET}/${KEY}" "${TMP}/app.tgz"
mkdir -p "$APP_DIR"
tar xzf "${TMP}/app.tgz" -C "$APP_DIR"

if [[ ! -d "${VENV}" ]]; then
  python3.11 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

if ! grep -q '^SECRET_KEY=' /etc/nfl-quiz.env 2>/dev/null; then
  echo "SECRET_KEY=$(openssl rand -hex 32)" >> /etc/nfl-quiz.env
fi

systemctl daemon-reload
systemctl enable nfl-quiz
systemctl restart nfl-quiz
systemctl is-active nfl-quiz
