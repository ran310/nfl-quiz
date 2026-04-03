#!/bin/bash
# CodeDeploy runs ApplicationStop using the *previous* deployment's bundle on this instance.
# With one shared deployment group for all nginx apps, that script would belong to another
# repo and would stop *that* service (e.g. project-showcase on /). Do not stop services here.
# Stop this app in before_install.sh instead (current bundle).
set -euo pipefail
exit 0
