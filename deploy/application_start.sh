#!/bin/bash
# CodeDeploy lifecycle: ApplicationStart — systemd unit matches aws-infra ec2-nginx-stack user data.
set -euxo pipefail

cat > /etc/systemd/system/nfl-quiz.service <<'UNIT'
[Unit]
Description=NFL Quiz (Gunicorn)
After=network.target
ConditionPathExists=/opt/nfl-quiz/venv/bin/gunicorn

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

systemctl daemon-reload
systemctl enable nfl-quiz
systemctl restart nfl-quiz
systemctl is-active nfl-quiz
