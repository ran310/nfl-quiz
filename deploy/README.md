# nfl-quiz AWS deployment

## Overview

**nfl-quiz** is a small **NFL stats quiz** web app: players and seasons are compared in the browser, with questions driven from bundled data and the ESPN API stack (`pyespn`). It is a **toy project** meant for **learning AWS and deployment automation**, not production traffic or serious reliability targets.

The live app is **hosted on AWS**: a single **EC2** instance (from a separate CDK repo) runs **nginx** as the front door and **Gunicorn** for the Python **Flask** app. **GitHub Actions** packages the repo (with **`appspec.yml`** and **`deploy/*.sh`**), uploads a **zip** to **S3**, and starts an **AWS CodeDeploy** deployment against the **shared** nginx EC2 deployment group—so day-to-day work stays in code and config instead of the AWS console.

The EC2 stack defines **one** CodeDeploy application and deployment group for **all** co-hosted apps (health dashboard, nfl-quiz, project-showcase, deephaven-experiments). Only run **one** deployment at a time on that group so lifecycle hooks do not overlap.

This **`deploy/`** folder documents that path: IAM for CI, optional local deploy commands, and troubleshooting.

---

In production for this setup, the app is served under **`/nfl-quiz/`** on the **`AwsInfra-Ec2Nginx`** host (nginx reverse proxy → Gunicorn on `127.0.0.1:8080`). Shared infrastructure (VPC, Elastic IP, S3 artifact bucket, nginx, systemd) is defined in **`aws-experimentation/aws-infra`**.

## One-time: IAM for GitHub Actions (OIDC)

Create an IAM role trusted by `token.actions.githubusercontent.com` for your repository, with a policy similar to:

- `cloudformation:DescribeStacks` on `AwsInfra-Ec2Nginx` (or `*` for the account)
- `s3:PutObject`, `s3:ListBucket` on the artifact bucket (name from stack output `Ec2NginxArtifactBucketName`)
- `codedeploy:CreateDeployment`, `codedeploy:RegisterApplicationRevision`, `codedeploy:GetDeployment`, `codedeploy:GetDeploymentConfig`, `codedeploy:GetApplicationRevision` on the CodeDeploy app from outputs **`CodeDeployAppName`** / **`CodeDeployDeploymentGroupName`**

Set GitHub secret **`AWS_ROLE_TO_ASSUME`** to that role ARN. Set repository variable or secret **`AWS_REGION`** (e.g. `us-east-1`).

## Deploy

- **CI:** workflow **Deploy to AWS** zips the repo (including **`appspec.yml`**), uploads to `s3://…/nfl-quiz/releases/<sha>.zip`, then **`aws deploy create-deployment`** and waits for success.
- **Local:** with AWS CLI configured, from repo root (mirror CI):

```bash
export AWS_REGION=us-east-1
STACK=AwsInfra-Ec2Nginx
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='Ec2NginxArtifactBucketName'].OutputValue" --output text)
APP=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='CodeDeployAppName'].OutputValue" --output text)
DG=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='CodeDeployDeploymentGroupName'].OutputValue" --output text)
KEY="nfl-quiz/releases/local-$(git rev-parse HEAD).zip"
zip -r /tmp/nfl-quiz.zip . -x '*/.git/*' -x '.git/*' -x '*.pyc' -x '*__pycache__/*'
aws s3 cp /tmp/nfl-quiz.zip "s3://${BUCKET}/${KEY}"
DEPLOYMENT_ID=$(aws deploy create-deployment --application-name "$APP" --deployment-group-name "$DG" \
  --s3-location "bucket=${BUCKET},key=${KEY},bundleType=zip" --query deploymentId --output text)
aws deploy wait deployment-successful --deployment-id "$DEPLOYMENT_ID"
```

Legacy tarball + **`deploy/remote-install.sh`** via SSM is unused by CI; you can still run that script on the host manually if needed.

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

CodeDeploy **ApplicationStart** writes **`/etc/systemd/system/nfl-quiz.service`**. Re-run **Deploy to AWS** after hook script changes.

## `python3.11: command not found` on deploy

The install script prefers **`python3.11`**, then falls back to **`python3`**. If the instance was created before CDK installed Python, run once (SSM or Session Manager):

`sudo dnf install -y python3.11 python3.11-pip`

—or redeploy **`AwsInfra-Ec2Nginx`** so current user data runs—then re-run the GitHub deploy.
