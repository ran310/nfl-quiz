#!/bin/bash
# Run on the EC2 nginx host (via SSM). Args: <s3-bucket> <s3-key>
# App + systemd only; nginx vhost is aws-infra CDK (ec2-nginx-stack.ts).
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

# Prefer 3.11 if present (matches CDK user data); else any python3 (AL2023 AMI variants differ).
if command -v python3.11 &>/dev/null; then
  PY=python3.11
elif command -v python3 &>/dev/null; then
  PY=python3
else
  echo "python3.11 and python3 not found; install Python on the host." >&2
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  "${PY}" -m venv "${VENV}"
fi
"${VENV}/bin/pip" install --upgrade pip
"${VENV}/bin/pip" install --no-cache-dir -r "${APP_DIR}/requirements.txt"

# Env for Gunicorn (must match nginx /nfl-quiz/ path in aws-infra).
if [[ ! -f /etc/nfl-quiz.env ]]; then
  echo 'APPLICATION_ROOT=/nfl-quiz' > /etc/nfl-quiz.env
elif ! grep -q '^APPLICATION_ROOT=' /etc/nfl-quiz.env 2>/dev/null; then
  echo 'APPLICATION_ROOT=/nfl-quiz' >> /etc/nfl-quiz.env
fi
if ! grep -q '^SECRET_KEY=' /etc/nfl-quiz.env 2>/dev/null; then
  echo "SECRET_KEY=$(openssl rand -hex 32)" >> /etc/nfl-quiz.env
fi

# Unit file normally comes from CDK user data; create it here if the instance predates that.
if [[ ! -f /etc/systemd/system/nfl-quiz.service ]]; then
  cat > /etc/systemd/system/nfl-quiz.service <<'UNIT'
[Unit]
Description=NFL Quiz (Gunicorn)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/nfl-quiz/app
EnvironmentFile=/etc/nfl-quiz.env
ExecStart=/opt/nfl-quiz/venv/bin/gunicorn --bind 127.0.0.1:8080 app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
fi

# Nginx /nfl-quiz/ → :8080 is defined only in aws-infra (ec2-nginx-stack user data).

systemctl daemon-reload
systemctl enable nfl-quiz
systemctl restart nfl-quiz
systemctl is-active nfl-quiz
