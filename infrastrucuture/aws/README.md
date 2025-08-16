# Newsletter Automation Platform – AWS Infrastructure

> Terraform-deployed, serverless newsletter pipeline that generates, approves, and delivers HTML newsletters on a schedule or on-demand.

---

## 🏗️ Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ EventBridge     │────▶│ AWS Batch    │────▶│ S3 newsletters  │
│ (cron / rate)   │     │ (container)  │     │ bucket          │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                │                        │
┌─────────────────┐     ┌──────────────┐               │
│ Lambda Approval │◀────│ S3 Event     │               │
│                 │     │ Notification │               │
└─────────────────┘     └──────────────┘               │
                                │                        │
┌─────────────────┐     ┌──────────────┐               │
│ Lambda Sender   │◀────│ API Gateway  │◀──────────────┘
│                 │     │ approval URL │
└─────────────────┘     └──────────────┘
```

---

## 📦 Resources Created

| Resource | Purpose |
|---|---|
| **Compute** | |
| `AWS Batch` job queue & compute env | Runs the container that generates newsletters |
| **Storage** | |
| `S3` *newsletter-bucket-xxxx* | Stores generated HTML newsletters |
| `S3` *newsletter-subscribers-xxxx* | Stores subscriber CSV files |
| `S3` *newsletter-athena-results-xxxx* | Athena query results |
| **Workflow** | |
| `EventBridge` rule | Triggers the Batch job on schedule |
| `Lambda` approval-sender | Emails admin link when newsletter ready |
| `Lambda` bulk-sender | Sends approved newsletter to all subscribers |
| `API Gateway` `/approve` endpoint | One-click approval & send |
| **Auth & IAM** | |
| `IAM` roles | Least-privilege for Batch, Lambda, EventBridge |
| **Observability** | |
| `CloudWatch Logs` groups | All stdout/stderr from Batch & Lambda |
| `AWS Budgets` | Monthly **$200** cost alert |

---

## 🚀 Quick Start

### 1. Prerequisites
- AWS CLI profile with **AdministratorAccess** (or least-privilege as per `iam/` dir)  
- Terraform ≥ 1.5  
- Docker (to build & push image)

### 2. One-time Setup
```bash
# 1. Clone
git clone <repo>
cd newsletter-infra

# 2. ECR repo (first time only)
aws ecr create-repository --repository-name newsletter-generator --region eu-central-1

# 3. Login & push your container
aws ecr get-login-password --region eu-central-1 | \
  docker login --username AWS --password-stdin <acct>.dkr.ecr.eu-central-1.amazonaws.com

docker build -t newsletter-generator .
docker tag newsletter-generator:latest <acct>.dkr.ecr.eu-central-1.amazonaws.com/newsletter-generator:1.0.0
docker push <acct>.dkr.ecr.eu-central-1.amazonaws.com/newsletter-generator:1.0.0
```

### 3. Deploy
```bash
export TF_VAR_ecr_repository_uri=<acct>.dkr.ecr.eu-central-1.amazonaws.com/newsletter-generator:1.0.0
terraform init
terraform plan
terraform apply
```

### 4. Bedrock
You need to enable access to the model that agents are going to use. 

As of **August 2025**, **Amazon Bedrock model access must be enabled manually through the AWS Management Console**:
- Navigate to **Amazon Bedrock → Model Access**.
- Select the desired models (e.g., Claude 3.5 Sonnet).
- Complete the subscription flow (including EULA acceptance).

### ✅ **What you *can* do via CLI/API after access is granted**:
- **List available models**:
  ```bash
  aws bedrock list-foundation-models --region us-east-1
  ```

### 🔧 **Action required**:
1. **Log in to the AWS Console**.
2. Go to **Bedrock → Model Access**.
3. **Enable the models** you need (e.g., Claude 3.5 Sonnet).
4. Wait ~5 minutes for propagation.


---

## 📥 Subscriber Data

| File | Location | Format |
|---|---|---|
| Master list | `s3://newsletter-subscribers-xxxx/subscribers.csv` | CSV, **no header**<br>`email,name,subscribed_date` |
| Segments | `s3://newsletter-subscribers-xxxx/lists/*.csv` | same |

Upload example:
```bash
BUCKET=$(terraform output -raw subscribers_bucket_name)
cat > tech.csv <<EOF
alice@example.com,Alice,2024-08-07
bob@example.com,Bob,2024-08-06
EOF
aws s3 cp tech.csv s3://$BUCKET/lists/tech.csv
```

---

## 🔐 API Keys (Secrets Manager)

1. Store once:
```bash
aws secretsmanager create-secret \
  --name newsletter/api-keys \
  --secret-string '{"TAVILY_API_KEY":"<key>","GEMINI_API_KEY":"<key>"}' \
  --region eu-central-1
```

2. The container fetches them at runtime (see `code/get_secrets.py`).

---

## 🕒 Schedule & Triggers

| Trigger | How to change |
|---|---|
| **Daily 09:00 UTC** | `terraform apply -var='newsletter_schedule="cron(0 9 * * ? *)"'` |
| **Every 12 h** | `terraform apply -var='newsletter_schedule="rate(12 hours)"'` |
| **Manual run** | AWS Console → Batch → Submit job → use `newsletter-generator-job` |

---

## 🔍 Operations

### View Logs
```bash
aws logs tail /aws/batch/newsletter-generator --follow
```

### Cost & Budgets
- Budget alert sent to `omransy1994@gmail.com` at **80 %** of **$200** monthly.
- Free-tier covers **t3.micro / t3.small** instances used by `instance_types = ["optimal"]`.

---

## 🔧 Useful Outputs

```bash
terraform output
newsletters_bucket_name = "newsletter-bucket-4fa2f9d2"
subscribers_bucket_name = "newsletter-subscribers-4fa2f9d2"
api_gateway_url         = "https://abcd1234.execute-api.eu-central-1.amazonaws.com/prod"
```

---

## 🧹 Teardown
```bash
terraform destroy
aws ecr delete-repository --repository-name newsletter-generator --force --region eu-central-1
```

---

## 📝 License
MIT – feel free to fork and adapt.