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

# Nginx must proxy /nfl-quiz/ → Gunicorn. Older hosts never got this from CDK user data; rewrite full vhost.
PROJECT_NAME="${NFL_QUIZ_PROJECT_NAME:-learn-aws}"
QUIZ_PATH="/nfl-quiz"
NGINX_CONF="/etc/nginx/conf.d/${PROJECT_NAME}-apps.conf"
mkdir -p /var/www/app1 /var/www/app2
cat > "$NGINX_CONF" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location = ${QUIZ_PATH} {
        return 301 ${QUIZ_PATH}/;
    }

    location ${QUIZ_PATH}/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${QUIZ_PATH};
    }

    location /app1/ {
        alias /var/www/app1/;
        index index.html;
    }
    location /app2/ {
        alias /var/www/app2/;
        index index.html;
    }
    location = / {
        default_type text/html;
        return 200 "<html><body><h1>${PROJECT_NAME} nginx</h1><p><a href=\"${QUIZ_PATH}/\">${QUIZ_PATH}/</a> (nfl-quiz) &middot; <a href=\"/app1/\">/app1/</a> &middot; <a href=\"/app2/\">/app2/</a></p></body></html>";
    }
}
EOF
nginx -t
systemctl reload nginx

systemctl daemon-reload
systemctl enable nfl-quiz
systemctl restart nfl-quiz
systemctl is-active nfl-quiz
