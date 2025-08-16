terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

provider "aws" {
  region = var.aws_region
}

# ------------------------------------------------------------------
# Bedrock model access CANNOT be enabled via Terraform.
# You must do this manually in the AWS Console:
# Bedrock → Model access → Enable Claude models
# ------------------------------------------------------------------

variable "admin_email" {
  description = "Admin email for approvals"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "newsletter_from_email" {
  description = "From email for newsletters"
  type        = string
}

variable "ecr_repository_uri" {
  description = "ECR repository URI for newsletter generator container"
  type        = string
}

variable "newsletter_schedule" {
  description = "Schedule expression for newsletter generation"
  type        = string
  default     = "cron(0 16 ? * FRI *)"
}

variable "limit_amount" {
  description = "Budget limit in USD"
  type        = string
  default     = "200"
}

variable "bedrock_model" {
  description = "Bedrock model identifier used by the Batch job and any other resources"
  type        = string
  default     = "bedrock:meta.llama3-2-3b-instruct-v1:0"
}

# ------------------------------------------------------------------
# Budgets
# ------------------------------------------------------------------
resource "aws_budgets_budget" "neuz_budget" {
  name         = "Ze-Neuz-lettah-Aye-gendt-Budget"
  budget_type  = "COST"
  time_unit    = "MONTHLY"
  limit_amount = var.limit_amount
  limit_unit   = "USD"

  cost_types {
    include_tax          = true
    include_subscription = true
    use_blended          = false
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.admin_email]
  }
}

# ------------------------------------------------------------------
# Data sources
# ------------------------------------------------------------------
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

# ------------------------------------------------------------------
# S3 Buckets
# ------------------------------------------------------------------
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "newsletters" {
  bucket = "newsletter-bucket-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "newsletters" {
  bucket = aws_s3_bucket.newsletters.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket" "subscribers" {
  bucket = "newsletter-subscribers-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "athena_results" {
  bucket = "newsletter-athena-results-${random_id.bucket_suffix.hex}"
}

# ------------------------------------------------------------------
# ECR
# ------------------------------------------------------------------
resource "aws_ecr_repository" "newsletter_generator" {
  name                 = "newsletter-generator"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ------------------------------------------------------------------
# VPC
# ------------------------------------------------------------------
resource "aws_vpc" "newsletter_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "newsletter-vpc"
    Environment = var.environment
  }
}

resource "aws_internet_gateway" "newsletter_igw" {
  vpc_id = aws_vpc.newsletter_vpc.id

  tags = {
    Name        = "newsletter-igw"
    Environment = var.environment
  }
}

# Public subnets (for NAT gateways)
resource "aws_subnet" "public_subnets" {
  count                   = 2
  vpc_id                  = aws_vpc.newsletter_vpc.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name        = "newsletter-public-subnet-${count.index + 1}"
    Environment = var.environment
    Type        = "Public"
  }
}

# Private subnets (for Batch)
resource "aws_subnet" "private_subnets" {
  count             = 2
  vpc_id            = aws_vpc.newsletter_vpc.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name        = "newsletter-private-subnet-${count.index + 1}"
    Environment = var.environment
    Type        = "Private"
  }
}

# Elastic IPs for NAT
resource "aws_eip" "nat_eips" {
  count  = 2
  domain = "vpc"

  tags = {
    Name        = "newsletter-nat-eip-${count.index + 1}"
    Environment = var.environment
  }
}

resource "aws_nat_gateway" "nat_gateways" {
  count         = 2
  allocation_id = aws_eip.nat_eips[count.index].id
  subnet_id     = aws_subnet.public_subnets[count.index].id

  tags = {
    Name        = "newsletter-nat-gateway-${count.index + 1}"
    Environment = var.environment
  }
}

# Route tables
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.newsletter_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.newsletter_igw.id
  }

  tags = {
    Name        = "newsletter-public-rt"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "public_rta" {
  count          = 2
  subnet_id      = aws_subnet.public_subnets[count.index].id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table" "private_rt" {
  count  = 2
  vpc_id = aws_vpc.newsletter_vpc.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat_gateways[count.index].id
  }

  tags = {
    Name        = "newsletter-private-rt-${count.index + 1}"
    Environment = var.environment
  }
}

resource "aws_route_table_association" "private_rta" {
  count          = 2
  subnet_id      = aws_subnet.private_subnets[count.index].id
  route_table_id = aws_route_table.private_rt[count.index].id
}

# Security group
resource "aws_security_group" "batch_security_group" {
  name        = "newsletter-batch-sg"
  description = "Security group for newsletter batch instances"
  vpc_id      = aws_vpc.newsletter_vpc.id

  egress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "DNS UDP"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "DNS TCP"
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "NTP"
    from_port   = 123
    to_port     = 123
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "newsletter-batch-sg"
    Environment = var.environment
  }
}

# ------------------------------------------------------------------
# IAM Roles
# ------------------------------------------------------------------
resource "aws_iam_role" "batch_service_role" {
  name = "newsletter-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "batch.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_service_role_policy" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

resource "aws_iam_role" "batch_instance_role" {
  name = "newsletter-batch-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "batch_instance_role_policy" {
  role       = aws_iam_role.batch_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_instance_profile" "batch_instance_profile" {
  name = "newsletter-batch-instance-profile"
  role = aws_iam_role.batch_instance_role.name
}

resource "aws_iam_role" "batch_execution_role" {
  name = "newsletter-batch-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "batch_execution_policy" {
  name = "newsletter-batch-execution-policy"
  role = aws_iam_role.batch_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:PutObjectAcl", "s3:GetObject"]
        Resource = ["${aws_s3_bucket.newsletters.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:newsletter/api-keys*"
      },
      {
        Effect   = "Allow"
        Action   = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/${replace(var.bedrock_model, "bedrock:", "")}"
        ]

      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:GetFoundationModel", "bedrock:ListFoundationModels"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "batch_execution_role_policy" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------------------
# Batch
# ------------------------------------------------------------------
resource "aws_batch_compute_environment" "newsletter_compute_env" {
  compute_environment_name = "newsletter-compute-env"
  type                     = "MANAGED"
  state                    = "ENABLED"
  service_role             = aws_iam_role.batch_service_role.arn

  compute_resources {
    type                = "EC2"
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    min_vcpus           = 1
    max_vcpus           = 4
    desired_vcpus       = 1
    instance_type       = ["optimal"]
    subnets             = aws_subnet.private_subnets[*].id
    security_group_ids  = [aws_security_group.batch_security_group.id]
    instance_role       = aws_iam_instance_profile.batch_instance_profile.arn

    tags = {
      Name        = "newsletter-batch-instance"
      Environment = var.environment
    }
  }

  depends_on = [aws_iam_role_policy_attachment.batch_service_role_policy]
}

resource "aws_batch_job_queue" "newsletter_job_queue" {
  name     = "newsletter-job-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.newsletter_compute_env.arn
  }
}

resource "aws_cloudwatch_log_group" "batch_logs" {
  name              = "/aws/batch/newsletter-generator"
  retention_in_days = 14
}

resource "aws_batch_job_definition" "newsletter_job_def" {
  name = "newsletter-generator-job"
  type = "container"

  container_properties = jsonencode({
    image       = var.ecr_repository_uri
    vcpus       = 2
    memory      = 2048
    jobRoleArn  = aws_iam_role.batch_execution_role.arn
    environment = [
      { name = "S3_BUCKET", value = aws_s3_bucket.newsletters.bucket },
      { name = "AWS_DEFAULT_REGION", value = var.aws_region }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"  = aws_cloudwatch_log_group.batch_logs.name
        "awslogs-region" = var.aws_region
      }
    }
    command = ["uv", "run", "python", "src/main.py", "--runs", "on_aws", "--model", "bedrock:anthropic.claude-3-5-sonnet-20240620-v1:0"]
  })

  retry_strategy { attempts = 2 }
  timeout { attempt_duration_seconds = 3600 }

  depends_on = [aws_iam_role.batch_execution_role]
}

# ------------------------------------------------------------------
# EventBridge
# ------------------------------------------------------------------
resource "aws_iam_role" "eventbridge_batch_role" {
  name = "newsletter-eventbridge-batch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_batch_policy" {
  name = "newsletter-eventbridge-batch-policy"
  role = aws_iam_role.eventbridge_batch_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["batch:SubmitJob"]
        Resource = [aws_batch_job_queue.newsletter_job_queue.arn, aws_batch_job_definition.newsletter_job_def.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["batch:DescribeJobs", "batch:DescribeJobQueues", "batch:DescribeJobDefinitions"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "newsletter_schedule" {
  name                = "newsletter-generation-schedule"
  description         = "Trigger newsletter generation every Friday at 16:00 UTC"
  schedule_expression = var.newsletter_schedule
  state               = "ENABLED"
}

resource "aws_cloudwatch_event_target" "batch_target" {
  rule      = aws_cloudwatch_event_rule.newsletter_schedule.name
  target_id = "NewsletterBatchTarget"
  arn       = aws_batch_job_queue.newsletter_job_queue.arn
  role_arn  = aws_iam_role.eventbridge_batch_role.arn

  batch_target {
    job_definition = aws_batch_job_definition.newsletter_job_def.name
    job_name       = "newsletter-generation-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  }
}

# ------------------------------------------------------------------
# IAM Roles for Lambdas
# ------------------------------------------------------------------
resource "aws_iam_role" "approval_lambda_role" {
  name = "newsletter-approval-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "approval_lambda_policy" {
  name = "newsletter-approval-lambda-policy"
  role = aws_iam_role.approval_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.newsletters.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "sender_lambda_role" {
  name = "newsletter-sender-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "sender_lambda_policy" {
  name = "newsletter-sender-lambda-policy"
  role = aws_iam_role.sender_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${aws_s3_bucket.newsletters.arn}/*", "${aws_s3_bucket.subscribers.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["glue:GetTable", "glue:GetPartitions"]
        Resource = "*"
      }
    ]
  })
}

# ------------------------------------------------------------------
# Lambda functions (with custom log groups & auto-redeploy)
# ------------------------------------------------------------------
data "archive_file" "approval_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/approval_lambda.zip"
  source {
    content  = file("${path.module}/approval_lambda.py")
    filename = "lambda_function.py"
  }
}

data "archive_file" "sender_lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/sender_lambda.zip"
  source {
    content  = file("${path.module}/sender_lambda.py")
    filename = "lambda_function.py"
  }
}

resource "aws_lambda_function" "approval_lambda" {
  filename         = data.archive_file.approval_lambda_zip.output_path
  function_name    = "newsletter-approval-lambda"
  role             = aws_iam_role.approval_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  timeout          = 30
  source_code_hash = data.archive_file.approval_lambda_zip.output_base64sha256

  environment {
    variables = {
      ADMIN_EMAIL     = var.admin_email
      API_GATEWAY_URL = "https://${aws_api_gateway_rest_api.newsletter_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.newsletter_api_stage.stage_name}"
      FROM_EMAIL      = var.newsletter_from_email
    }
  }

  depends_on = [aws_cloudwatch_log_group.approval_lambda_logs]
}

resource "aws_lambda_function" "sender_lambda" {
  filename         = data.archive_file.sender_lambda_zip.output_path
  function_name    = "newsletter-sender-lambda"
  role             = aws_iam_role.sender_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.9"
  timeout          = 300
  source_code_hash = data.archive_file.sender_lambda_zip.output_base64sha256

  environment {
    variables = {
      SUBSCRIBERS_BUCKET     = aws_s3_bucket.subscribers.bucket
      NEWSLETTERS_BUCKET     = aws_s3_bucket.newsletters.bucket
      FROM_EMAIL             = var.newsletter_from_email
      ATHENA_DATABASE        = aws_glue_catalog_database.newsletter_db.name
      ATHENA_TABLE           = aws_glue_catalog_table.subscribers_table.name
      ATHENA_OUTPUT_LOCATION = "s3://${aws_s3_bucket.athena_results.bucket}/"
    }
  }

  depends_on = [aws_cloudwatch_log_group.sender_lambda_logs]
}

# ------------------------------------------------------------------
# CloudWatch log groups (custom names)
# ------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "approval_lambda_logs" {
  name              = "/aws/lambda/newsletter-approval"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "sender_lambda_logs" {
  name              = "/aws/lambda/newsletter-sender"
  retention_in_days = 14
}

# ------------------------------------------------------------------
# API Gateway
# ------------------------------------------------------------------
resource "aws_api_gateway_rest_api" "newsletter_api" {
  name = "newsletter-api"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

resource "aws_api_gateway_resource" "approve" {
  rest_api_id = aws_api_gateway_rest_api.newsletter_api.id
  parent_id   = aws_api_gateway_rest_api.newsletter_api.root_resource_id
  path_part   = "approve"
}

resource "aws_api_gateway_method" "approve_get" {
  rest_api_id   = aws_api_gateway_rest_api.newsletter_api.id
  resource_id   = aws_api_gateway_resource.approve.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "approve_integration" {
  rest_api_id             = aws_api_gateway_rest_api.newsletter_api.id
  resource_id             = aws_api_gateway_resource.approve.id
  http_method             = aws_api_gateway_method.approve_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.sender_lambda.invoke_arn
}

resource "aws_api_gateway_deployment" "newsletter_api" {
  depends_on = [aws_api_gateway_integration.approve_integration]
  rest_api_id = aws_api_gateway_rest_api.newsletter_api.id
}

resource "aws_api_gateway_stage" "newsletter_api_stage" {
  deployment_id = aws_api_gateway_deployment.newsletter_api.id
  rest_api_id   = aws_api_gateway_rest_api.newsletter_api.id
  stage_name    = "prod"
}

# ------------------------------------------------------------------
# Lambda permissions
# ------------------------------------------------------------------
resource "aws_lambda_permission" "s3_invoke_approval_lambda" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.approval_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.newsletters.arn
}

resource "aws_lambda_permission" "api_gateway_invoke_sender_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.sender_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.newsletter_api.execution_arn}/*/*"
}

# ------------------------------------------------------------------
# S3 notification for approval Lambda
# ------------------------------------------------------------------
resource "aws_s3_bucket_notification" "newsletters" {
  bucket = aws_s3_bucket.newsletters.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.approval_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "newsletters/"
    filter_suffix       = ".html"
  }

  depends_on = [aws_lambda_permission.s3_invoke_approval_lambda]
}

# ------------------------------------------------------------------
# Athena / Glue
# ------------------------------------------------------------------
resource "aws_s3_bucket_policy" "athena_results_policy" {
  bucket = aws_s3_bucket.athena_results.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowAthena"
        Effect    = "Allow"
        Principal = { Service = "athena.amazonaws.com" }
        Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource  = "${aws_s3_bucket.athena_results.arn}/*"
      }
    ]
  })
}

resource "aws_s3_bucket_public_access_block" "athena_results_pab" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = false
  ignore_public_acls      = false
  block_public_policy     = false
  restrict_public_buckets = false
}

resource "aws_glue_catalog_database" "newsletter_db" {
  name = "newsletter_database"
}

resource "aws_glue_catalog_table" "subscribers_table" {
  name          = "subscribers"
  database_name = aws_glue_catalog_database.newsletter_db.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification"         = "csv"
    "skip.header.line.count" = "0"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.subscribers.bucket}/"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters            = { "field.delim" = "," }
    }

    columns {
      name = "email"
      type = "string"
    }
    columns {
      name = "name"
      type = "string"
    }
    columns {
      name = "subscribed_date"
      type = "string"
    }
  }
}

# ------------------------------------------------------------------
# Outputs
# ------------------------------------------------------------------
output "newsletters_bucket_name" {
  value = aws_s3_bucket.newsletters.bucket
}

output "subscribers_bucket_name" {
  value = aws_s3_bucket.subscribers.bucket
}

output "api_gateway_url" {
  value = "https://${aws_api_gateway_rest_api.newsletter_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.newsletter_api_stage.stage_name}"
}

output "approval_lambda_name" {
  value = aws_lambda_function.approval_lambda.function_name
}

output "sender_lambda_name" {
  value = aws_lambda_function.sender_lambda.function_name
}

output "batch_job_queue_name" {
  value = aws_batch_job_queue.newsletter_job_queue.name
}

output "batch_job_definition_name" {
  value = aws_batch_job_definition.newsletter_job_def.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.newsletter_generator.repository_url
}