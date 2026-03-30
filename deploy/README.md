# nfl-quiz AWS deployment

## Overview

**nfl-quiz** is a small **NFL stats quiz** web app: players and seasons are compared in the browser, with questions driven from bundled data and the ESPN API stack (`pyespn`). It is a **toy project** meant for **learning AWS and deployment automation**, not production traffic or serious reliability targets.

The live app is **hosted on AWS**: a single **EC2** instance (from a separate CDK repo) runs **nginx** as the front door and **Gunicorn** for the Python **Flask** app. **GitHub Actions** packages the repo, pushes artifacts to **S3**, and uses **Systems Manager (SSM)** to install and restart the app on the instance—so day-to-day work stays in code and config instead of the AWS console.

This **`deploy/`** folder documents that path: IAM for CI, optional local deploy commands, and troubleshooting.

---

In production for this setup, the app is served under **`/nfl-quiz/`** on the **`AwsInfra-Ec2Nginx`** host (nginx reverse proxy → Gunicorn on `127.0.0.1:8080`). Shared infrastructure (VPC, Elastic IP, S3 artifact bucket, nginx, systemd) is defined in **`aws-experimentation/aws-infra`**.

## One-time: IAM for GitHub Actions (OIDC)

Create an IAM role trusted by `token.actions.githubusercontent.com` for your repository, with a policy similar to:

- `cloudformation:DescribeStacks` on `AwsInfra-Ec2Nginx` (or `*` for the account)
- `s3:PutObject`, `s3:ListBucket` on the artifact bucket (name from stack output `Ec2NginxArtifactBucketName`)
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`

Restrict `ssm:SendCommand` to instances tagged `Project=<your projectName>` if you use tags from CDK.

Set GitHub secret **`AWS_ROLE_TO_ASSUME`** to that role ARN. Set repository variable or secret **`AWS_REGION`** (e.g. `us-east-1`).

## Deploy

- **CI:** workflow **Deploy to AWS** uploads a `git archive` tarball to `s3://…/nfl-quiz/releases/<sha>.tar.gz` and runs `deploy/remote-install.sh` on the instance via SSM.
- **Local:** with AWS CLI configured, from repo root:

```bash
chmod +x deploy/remote-install.sh
export AWS_REGION=us-east-1
STACK=AwsInfra-Ec2Nginx
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='Ec2NginxArtifactBucketName'].OutputValue" --output text)
IID=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='NginxInstanceId'].OutputValue" --output text)
KEY="nfl-quiz/releases/local-$(git rev-parse HEAD).tar.gz"
git archive --format=tar.gz -o /tmp/nfl-quiz.tgz HEAD
aws s3 cp /tmp/nfl-quiz.tgz "s3://${BUCKET}/${KEY}"
B64=$(base64 -w0 deploy/remote-install.sh 2>/dev/null || base64 deploy/remote-install.sh | tr -d '\n')
PARAMS=$(jq -n --arg b64 "$B64" --arg b "$BUCKET" --arg k "$KEY" '{commands: ["echo \($b64) | base64 -d | bash -s \($b) \($k)"]}')
aws ssm send-command --instance-ids "$IID" --document-name AWS-RunShellScript --parameters "$PARAMS"
```

## Start / stop (no console)

- **App only:** `aws ssm send-command --instance-ids "$IID" --document-name AWS-RunShellScript --parameters '{"commands":["systemctl stop nfl-quiz"]}'`
- **App start:** `… "systemctl start nfl-quiz" …`
- **Whole EC2** (save compute; Elastic IP keeps the address): `aws ec2 stop-instances --instance-ids "$IID"` / `aws ec2 start-instances …`

## URLs

After deploy, open stack output **`NflQuizUrl`** (or `http://<NginxElasticIp>/nfl-quiz/`).

## `/` works but `/nfl-quiz/` returns 404

Nginx is defined only by **aws-infra** (`ec2-nginx-stack.ts` user data). The host is missing **`/nfl-quiz/`** routing if user data never ran or the config file was deleted. **Redeploy `AwsInfra-Ec2Nginx`**, or **replace** the instance, or restore **`/etc/nginx/conf.d/<projectName>-apps.conf`** from a fresh `cdk synth` / template, then **`sudo nginx -t && sudo systemctl reload nginx`**.

If you use a non-default CDK **`projectName`**, the conf file is **`/etc/nginx/conf.d/<projectName>-apps.conf`**—keep **`projectName`** in sync when debugging.

## `Unit file nfl-quiz.service does not exist`

The deploy script now **creates** `/etc/systemd/system/nfl-quiz.service` if it is missing (instances created before CDK added user data never had it). Re-run **Deploy to AWS** after pulling the latest `deploy/remote-install.sh`.

## `python3.11: command not found` on deploy

The install script prefers **`python3.11`**, then falls back to **`python3`**. If the instance was created before CDK installed Python, run once (SSM or Session Manager):

`sudo dnf install -y python3.11 python3.11-pip`

—or redeploy **`AwsInfra-Ec2Nginx`** so current user data runs—then re-run the GitHub deploy.
