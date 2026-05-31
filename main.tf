terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# -------------------------------------------------------------------
# VARIABLES
# -------------------------------------------------------------------
variable "bucket_name" {
  type    = string
  default = "sagemaker-s3-chidi"
}

variable "endpoint_arn" {
  type    = string
  default = "arn:aws:sagemaker:us-east-1:148622480762:endpoint/xgb-fraud-endpoint"
}

# -------------------------------------------------------------------
# IAM ROLE: Glue ETL Job
# -------------------------------------------------------------------
resource "aws_iam_role" "glue_role" {
  name = "fraud-glue-etl-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "glue.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "fraud-detection"
  }
}

resource "aws_iam_role_policy" "glue_policy" {
  role = aws_iam_role.glue_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      }
    ]
  })
}

# -------------------------------------------------------------------
# GLUE JOB: Fraud ETL
# -------------------------------------------------------------------
resource "aws_glue_job" "fraud_etl" {
  name     = "fraud-etl-job"
  role_arn = aws_iam_role.glue_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${var.bucket_name}/fraud/scripts/glue_etl.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"   = "python"
    "--TempDir"        = "s3://${var.bucket_name}/fraud/tmp/"
    "--enable-metrics" = "true"
  }

  glue_version      = "4.0"
  max_retries       = 1
  number_of_workers = 2
  worker_type       = "G.1X"

  tags = {
    Project = "fraud-detection"
  }
}

# -------------------------------------------------------------------
# IAM ROLE: SageMaker Pipeline
# -------------------------------------------------------------------
resource "aws_iam_role" "sagemaker_role" {
  name = "fraud-sagemaker-pipeline-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "sagemaker.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "fraud-detection"
  }
}

resource "aws_iam_role_policy" "sagemaker_policy" {
  role = aws_iam_role.sagemaker_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ],
        Resource = [
          "arn:aws:s3:::${var.bucket_name}",
          "arn:aws:s3:::${var.bucket_name}/*"
        ]
      },
      {
        Effect = "Allow",
        Action = ["sagemaker:InvokeEndpoint"],
        Resource = var.endpoint_arn
      }
    ]
  })
}

# -------------------------------------------------------------------
# SAGEMAKER PIPELINE
# -------------------------------------------------------------------
resource "aws_sagemaker_pipeline" "fraud_inference_pipeline" {
  pipeline_name         = "fraud-realtime-inference-pipeline"
  pipeline_display_name = "fraud-realtime-inference"

  role_arn            = aws_iam_role.sagemaker_role.arn
  pipeline_definition = file("${path.module}/pipeline_definition.json")

  tags = {
    Project = "fraud-detection"
  }
}

# -------------------------------------------------------------------
# AUTOMATION: S3 → EventBridge → Lambda → Glue Job
# -------------------------------------------------------------------

resource "aws_s3_bucket_notification" "fraud_bucket_notifications" {
  bucket      = var.bucket_name
  eventbridge = true
}

resource "aws_cloudwatch_event_rule" "fraud_raw_event_rule" {
  name        = "fraud-raw-folder-event"
  description = "Triggers Lambda when new data lands in fraud/raw"

  event_pattern = jsonencode({
    "source" : ["aws.s3"],
    "detail-type" : ["Object Created"],
    "detail" : {
      "bucket" : { "name" : [var.bucket_name] },
      "object" : { "key" : [{ "prefix" : "fraud/raw/" }] }
    }
  })
}

# -------------------------------------------------------------------
# LAMBDA: Start Glue Job
# -------------------------------------------------------------------

resource "aws_iam_role" "lambda_glue_role" {
  name = "lambda-start-glue-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_glue_policy" {
  role = aws_iam_role.lambda_glue_role.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = ["glue:StartJobRun"],
        Resource = aws_glue_job.fraud_etl.arn
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "start_glue_job" {
  function_name = "start-fraud-etl-job"
  role          = aws_iam_role.lambda_glue_role.arn
  handler       = "lambda_start_glue.handler"
  runtime       = "python3.9"

  filename         = "${path.module}/lambda_start_glue.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_start_glue.zip")
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_glue_job.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.fraud_raw_event_rule.arn
}

resource "aws_cloudwatch_event_target" "fraud_raw_to_lambda" {
  rule      = aws_cloudwatch_event_rule.fraud_raw_event_rule.name
  target_id = "start-fraud-etl-job"
  arn       = aws_lambda_function.start_glue_job.arn
}
