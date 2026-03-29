# nfl-quiz AWS deployment

The app is served under **`/nfl-quiz/`** on the `AwsInfra-Ec2Nginx` host (nginx reverse proxy → Gunicorn on `127.0.0.1:8080`). Infrastructure (Elastic IP, S3 artifact bucket, nginx, systemd unit) lives in **`aws-experimentation/aws-infra`**.

## One-time: IAM for GitHub Actions (OIDC)

Create an IAM role trusted by `token.actions.githubusercontent.com` for your repository, with a policy similar to:

- `cloudformation:DescribeStacks` on `AwsInfra-Ec2Nginx` (or `*` for the account)
- `s3:PutObject`, `s3:ListBucket` on the artifact bucket (name from stack output `NflQuizArtifactBucketName`)
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
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK" --query "Stacks[0].Outputs[?OutputKey=='NflQuizArtifactBucketName'].OutputValue" --output text)
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
