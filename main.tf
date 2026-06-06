terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------
# Lambda Function
# -----------------------------
resource "aws_lambda_function" "start_pipeline" {
  function_name = "${var.pipeline_name}-starter"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.10"

  # Correct usage of path.module
  filename         = "${path.module}/${var.lambda_zip_path}"
  source_code_hash = filebase64sha256("${path.module}/${var.lambda_zip_path}")

  role = aws_iam_role.lambda_exec_role.arn
}

# -----------------------------
# IAM Role for Lambda
# -----------------------------
resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.pipeline_name}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# -----------------------------
# Outputs
# -----------------------------
output "lambda_function_name" {
  value = aws_lambda_function.start_pipeline.function_name
}

output "lambda_role_arn" {
  value = aws_iam_role.lambda_exec_role.arn
}
